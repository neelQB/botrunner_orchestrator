import os
import json
import uuid
import sqlite3
import psycopg2
from pathlib import Path
from psycopg2 import pool
from dataclasses import asdict
from pydantic import BaseModel
from abc import ABC, abstractmethod
from typing import Any, Optional, Type, Dict, List, Union

from emailbot.core.state import (
    ObjectionState,
    ProbingContext,
    UserContext,
    BotState,
    BotPersona,
)
from emailbot.core.state import (
    Products,
    ContactDetails,
    Leads,
    InputGuardrail,
    FollowupDetails,
    ProceedEmailDetails,
)
from emailbot.core.models import (
    NegotiationState,
    NegotiationAgentResponse,
    NegotiationConfig,
    Plan,
)
from emailbot.config.settings import logger
from emailbot.config import settings as _settings

from emailbot.core.state import (
    BotState,
    UserContext,
    BotPersona,
    Products,
    ContactDetails,
    Leads,
    LeadAnalysis,
    InputGuardrail,
    FollowupDetails,
    ProceedEmailDetails,
    NegotiationConfig,
    NegotiationState,
)


# Load environment variables (using cached singleton)

# ---------------------------------------------------------
#  SERIALIZATION LOGIC
# ---------------------------------------------------------


class PydanticEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Pydantic models and dataclasses."""

    def default(self, obj):
        if hasattr(obj, "model_dump"):  # Pydantic v2
            return obj.model_dump()
        elif hasattr(obj, "dict"):  # Pydantic v1
            return obj.dict()
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        return super().default(obj)


def serialize_state(state: Any) -> str:
    """Serialize BotState or other objects to JSON string."""
    if hasattr(state, "model_dump"):
        # Pydantic model
        state_dict = state.model_dump()
    elif hasattr(state, "__dataclass_fields__"):
        # Dataclass (legacy support)
        state_dict = asdict(state)
    elif isinstance(state, dict):
        state_dict = state
    else:
        state_dict = state
    return json.dumps(state_dict, cls=PydanticEncoder)


def deserialize_to_botstate(data: Union[str, dict]) -> BotState:
    """Reconstruct BotState dataclass from JSON string or dictionary."""
    if isinstance(data, str):
        data = json.loads(data)

    # helper to convert dict to object if needed
    def _to_obj(cls, val):
        if val is None:
            return None
        if isinstance(val, dict):
            return cls(**val)
        return val

    # 1. Reconstruct UserContext nested objects
    ctx_data = data.get("user_context", {})

    contact_details = _to_obj(ContactDetails, ctx_data.get("contact_details"))

    # Handle LeadAnalysis vs Leads discrepancy
    lead_details = ctx_data.get("lead_details")
    if lead_details:
        if isinstance(lead_details, dict):
            if "lead_classification" in lead_details:
                lead_details = LeadAnalysis(**lead_details)
            else:
                lead_details = Leads(**lead_details)

    followup_details = _to_obj(FollowupDetails, ctx_data.get("followup_details"))

    # 2. Reconstruct UserContext using Pydantic model_fields
    valid_ctx_fields = set(UserContext.model_fields.keys())
    user_context = UserContext(
        **{k: v for k, v in ctx_data.items() if k in valid_ctx_fields}
    )
    user_context.contact_details = contact_details
    user_context.lead_details = lead_details
    user_context.followup_details = followup_details

    # 3. Reconstruct BotPersona
    persona_data = data.get("bot_persona")
    bot_persona = None
    if persona_data:
        products = []
        for p in persona_data.get("company_products", []):
            if isinstance(p, dict):
                # Reconstruct Plan objects within the product
                raw_plans = p.get("plans") or []
                plan_objs = []
                for pl in raw_plans:
                    if isinstance(pl, dict):
                        plan_objs.append(Plan(**pl))
                    else:
                        plan_objs.append(pl)
                p["plans"] = plan_objs
            products.append(_to_obj(Products, p))

        valid_persona_fields = set(BotPersona.model_fields.keys())
        bot_persona = BotPersona(
            **{k: v for k, v in persona_data.items() if k in valid_persona_fields}
        )
        bot_persona.company_products = products

    # 4. Reconstruct Guardrail
    guardrail = _to_obj(InputGuardrail, data.get("input_guardrail_decision"))

    # 5. Reconstruct NegotiationState with NegotiationAgentResponse
    negotiation_data = data.get("negotiation_state", {})
    negotiation_session = None
    if negotiation_data and negotiation_data.get("negotiation_session"):
        logger.info(f"[deserialize_to_botstate] Found negotiation_session in data: {negotiation_data.get('negotiation_session').keys()}")
        negotiation_session = _to_obj(NegotiationAgentResponse, negotiation_data.get("negotiation_session"))
        logger.info(f"[deserialize_to_botstate] Reconstructed NegotiationAgentResponse - current_product={negotiation_session.current_product_id}, products_count={len(negotiation_session.negotiated_products)}")
    else:
        logger.info(f"[deserialize_to_botstate] No negotiation_session found in data")
    
    negotiation_config = None
    if negotiation_data and negotiation_data.get("negotiation_config"):
        negotiation_config = _to_obj(NegotiationConfig, negotiation_data.get("negotiation_config"))
    
    negotiation_kwargs = {}
    if negotiation_config is not None:
        negotiation_kwargs["negotiation_config"] = negotiation_config
    if negotiation_data:
        negotiation_kwargs["internal_note"] = negotiation_data.get("internal_note")
        negotiation_kwargs["negotiation_session"] = negotiation_session

    negotiation_state = NegotiationState(**negotiation_kwargs)

    return BotState(
        user_context=user_context,
        bot_persona=bot_persona,
        session_id=data.get("session_id"),
        conversation_id=data.get("conversation_id"),
        input_guardrail_decision=guardrail,
        response=data.get("response"),
        probing_context=_to_obj(ProbingContext, data.get("probing_context")),
        objection_state=_to_obj(ObjectionState, data.get("objection_state")),
        negotiation_state=negotiation_state,
    )


# ---------------------------------------------------------
#  BASE INTERFACE
# ---------------------------------------------------------


class SessionManagerBase(ABC):
    @abstractmethod
    def init_db(self) -> None:
        """Initialize database tables/connections."""
        pass

    @abstractmethod
    def save_state(self, user_id: str, state: BotState) -> None:
        """Save BotState to database."""
        pass

    @abstractmethod
    def load_state(self, user_id: str, model_type: Any) -> Optional[Any]:
        """Load state for a user."""
        pass

    @abstractmethod
    def get_or_create_session(
        self, user_id: Optional[str], model_type=BotState
    ) -> BotState:
        """Get existing session or create a new one."""
        pass


# ---------------------------------------------------------
#  SQLITE DRIVER
# ---------------------------------------------------------


class SQLiteSessionManager(SessionManagerBase):
    def __init__(self):
        self.base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.db_name = os.path.join(self.base_dir, "data", "chat_history.db")
        self.state_table = "session_state"

    def init_db(self):
        Path(os.path.join(self.base_dir, "data")).mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_name)
        cur = conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.state_table} (
                user_id TEXT PRIMARY KEY,
                state_json TEXT NOT NULL
            );
        """
        )
        conn.commit()
        conn.close()
        logger.info("SQLite database initialized successfully")

    def save_state(self, user_id: str, state: BotState) -> None:
        try:
            state_json = serialize_state(state)
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute(
                f"INSERT OR REPLACE INTO {self.state_table} (user_id, state_json) VALUES (?, ?)",
                (user_id, state_json),
            )
            conn.commit()
            conn.close()
            logger.info(f"State saved to SQLite for user_id={user_id}")
        except Exception as e:
            logger.error(f"Error saving state to SQLite for user_id={user_id}: {e}")
            raise

    def load_state(self, user_id: str, model_type: Any) -> Optional[Any]:
        try:
            conn = sqlite3.connect(self.db_name)
            cur = conn.cursor()
            cur.execute(
                f"SELECT state_json FROM {self.state_table} WHERE user_id = ?",
                (user_id,),
            )
            row = cur.fetchone()
            conn.close()

            if not row:
                return None

            if model_type == BotState:
                return deserialize_to_botstate(row[0])

            if hasattr(model_type, "model_validate_json"):
                return model_type.model_validate_json(row[0])
            return json.loads(row[0])
        except Exception as e:
            logger.error(f"Failed loading state from SQLite for {user_id}: {e}")
            logger.warning(f"Returning None to create fresh session for user {user_id}")
            # Return None to create a fresh session instead of propagating the error
            return None

    def get_or_create_session(
        self, user_id: Optional[str], model_type=BotState
    ) -> BotState:
        if user_id:
            loaded = self.load_state(user_id, model_type)
            if loaded:
                if hasattr(loaded, "user_context"):
                    loaded.user_context.user_id = user_id
                # DEBUG: Log if negotiation state was loaded
                if hasattr(loaded, "negotiation_state") and loaded.negotiation_state and loaded.negotiation_state.negotiation_session:
                    ns = loaded.negotiation_state.negotiation_session
                    logger.info(f"[SQLiteSessionManager] ✓ Loaded existing session - current_product={ns.current_product_id}, products_count={len(ns.negotiated_products)}")
                return loaded

        if not user_id:
            user_id = str(uuid.uuid4())
            logger.info(f"Generated new user_id: {user_id}")
        else:
            logger.info(f"Creating new session for provided user_id: {user_id}")

        state = BotState(
            user_context=UserContext(
                user_id=user_id,
                user_query="",
                chat_history=[],
            ),
            bot_persona=None,
            probing_context=ProbingContext(),
            objection_state=ObjectionState(),
            negotiation_state=NegotiationState(
                negotiation_config=NegotiationConfig(
                    max_discount_percent=5.0,
                    currency="INR",
                )
            ),
        )
        self.save_state(user_id, state)
        return state


# ---------------------------------------------------------
#  NEON DRIVER
# ---------------------------------------------------------


class NeonSessionManager(SessionManagerBase):
    def __init__(self):
        self.connection_pool = None
        # self.database_url = os.getenv("DATABASE_URL")
        self.database_url = _settings.database_url
        self.state_table = "session_state"

    def init_db(self):
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable is not set.")

        try:
            if self.connection_pool is None:
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 10, self.database_url
                )
                logger.info("PostgreSQL connection pool created successfully")

            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.state_table} (
                    user_id TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL
                );
            """
            )
            conn.commit()
            cur.close()
            self.connection_pool.putconn(conn)
            logger.info("Neon database tables initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Neon database: {e}")
            raise

    def save_state(self, user_id: str, state: BotState) -> None:
        conn = None
        try:
            state_json = serialize_state(state)
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            cur.execute(
                f"""INSERT INTO {self.state_table} (user_id, state_json) 
                    VALUES (%s, %s)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET state_json = EXCLUDED.state_json""",
                (user_id, state_json),
            )
            conn.commit()
            cur.close()
            self.connection_pool.putconn(conn)
            logger.info(f"State saved to Neon for user_id={user_id}")
        except Exception as e:
            logger.error(f"Error saving state to Neon for user_id={user_id}: {e}")
            if conn:
                self.connection_pool.putconn(conn)
            raise

    def load_state(self, user_id: str, model_type: Any) -> Optional[Any]:
        conn = None
        try:
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            cur.execute(
                f"SELECT state_json FROM {self.state_table} WHERE user_id = %s;",
                (user_id,),
            )
            row = cur.fetchone()
            cur.close()
            self.connection_pool.putconn(conn)

            if not row:
                return None

            if model_type == BotState:
                return deserialize_to_botstate(row[0])

            if hasattr(model_type, "model_validate_json"):
                return model_type.model_validate_json(row[0])
            return json.loads(row[0])
        except Exception as e:
            logger.error(f"Failed loading state from Neon for {user_id}: {e}")
            if conn:
                self.connection_pool.putconn(conn)
            return None

    def get_or_create_session(
        self, user_id: Optional[str], model_type=BotState
    ) -> BotState:
        if user_id:
            loaded = self.load_state(user_id, model_type)
            if loaded:
                if hasattr(loaded, "user_context"):
                    loaded.user_context.user_id = user_id
                # DEBUG: Log if negotiation state was loaded
                if hasattr(loaded, "negotiation_state") and loaded.negotiation_state and loaded.negotiation_state.negotiation_session:
                    ns = loaded.negotiation_state.negotiation_session
                    logger.info(f"[NeonSessionManager] ✓ Loaded existing session - current_product={ns.current_product_id}, products_count={len(ns.negotiated_products)}")
                return loaded

        if not user_id:
            user_id = str(uuid.uuid4())
            logger.info(f"Generated new user_id: {user_id}")
        else:
            logger.info(f"Creating new session for provided user_id: {user_id}")

        state = BotState(
            user_context=UserContext(
                user_id=user_id,
                user_query="",
                chat_history=[],
            ),
            bot_persona=None,
            probing_context=ProbingContext(),
            objection_state=ObjectionState(),
        )
        self.save_state(user_id, state)
        return state


def get_session_manager():
    # db_type = os.getenv("DATABASE", "sqlite").lower()
    db_type = _settings.database_type.lower()

    if db_type == "neon":
        logger.info("Using Neon (PostgreSQL) session manager")
        return NeonSessionManager()
    else:
        logger.info("Using SQLite session manager")
        return SQLiteSessionManager()


# Export singleton instance and its methods
_manager = get_session_manager()

init_memory_db = _manager.init_db
save_state = _manager.save_state
load_state = _manager.load_state
get_or_create_session = _manager.get_or_create_session
