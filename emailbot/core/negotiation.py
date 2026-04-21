from typing import Optional, Dict, Any, List
from emailbot.config.settings import logger
from emailbot.core.models import BotState, NegotiationAgentResponse, NegotiatedProduct

class NegotiationEngine:
    """
    Core engine for handling negotiation state updates and product detection.
    Operates on the per-product negotiated_products list.
    Separates system-managed state (pricing) from LLM-managed state (strategy).
    """
    
    def __init__(self, state: BotState):
        self.state = state

    ## Helpers
    def _ensure_session(self, source: str = "NegotiationEngine") -> NegotiationAgentResponse:
        """Ensure negotiation_session exists and return it."""
        ns = self.state.negotiation_state
        if not ns.negotiation_session:
            ns.negotiation_session = NegotiationAgentResponse(
                response=f"Initialized by {source}"
            )
        return ns.negotiation_session

    def _find_negotiated_product(self, product_id: str, product_name: str = None) -> Optional[NegotiatedProduct]:
        """Find an existing NegotiatedProduct entry by product_id, with name-based fallback."""
        session = self.state.negotiation_state.negotiation_session
        if not session:
            return None
        # 1. Exact ID match (highest priority)
        for np in session.negotiated_products:
            if np.product_id == product_id:
                return np
        # 2. Name-based fallback (LLM may return wrong/hallucinated product_id)
        if product_name:
            name_norm = product_name.strip().lower()
            for np in session.negotiated_products:
                if np.product_name and np.product_name.strip().lower() == name_norm:
                    logger.warning(f"[NegotiationEngine] ID mismatch for '{product_name}' — matched by name instead (LLM ID: {product_id}, actual ID: {np.product_id})")
                    return np
        return None

    ## Pre-detection
    def pre_detect_product(self, user_query: str) -> None:
        """
        Scan user query for product names or IDs before agent execution.
        IMPORTANT: Only switches product if explicitly mentioned in user_query.
        Does NOT override active negotiation unless new product is clearly mentioned.
        """
        if not user_query:
            return

        # accessible products
        products = self.state.bot_persona.company_products or []
        if not products:
            return

        # PRESERVE CURRENT PRODUCT: Check if there's an active negotiation
        session = self._ensure_session("Pre-Detection")
        current_product_id = session.current_product_id
        if current_product_id:
            logger.info(f"[NegotiationEngine] Current active product: {current_product_id}")

        # Check for matches
        query_norm = user_query.lower().strip()
        matched_product = None

        for p in products:
            p_name_norm = p.name.strip().lower()
            p_id_norm = p.id.strip().lower() if p.id else ""
            
            # 1. ID Match (Highest Priority)
            if p_id_norm and p_id_norm in query_norm.split(): # Token match for ID
                matched_product = p
                logger.info(f"[NegotiationEngine] Pre-detected product '{p.name}' via ID match '{p.id}'")
                break
            
            # 2. Exact Name Match
            if p_name_norm == query_norm:
                matched_product = p
                logger.info(f"[NegotiationEngine] Pre-detected product '{p.name}' via exact name match")
                break

            # 3. Token-based Name Match (ignoring spaces)
            if p_name_norm.replace(" ", "") in query_norm.replace(" ", ""):
                matched_product = p
                logger.info(f"[NegotiationEngine] Pre-detected product '{p.name}' via token match")
                break
            
            # 4. Substring Match (Lowest Priority)
            if p_name_norm in query_norm:
                matched_product = p
                logger.info(f"[NegotiationEngine] Pre-detected product '{p.name}' via substring match")

        if matched_product:
            self._apply_product_to_state(matched_product, source="Pre-Detection")

    ## State update from LLM output
    def update_negotiation_state(self, output_data: Dict[str, Any]) -> None:
        """
        Update negotiation state based on LLM output.
        Now works with negotiated_products list: merges only products the LLM returned.
        """
        session = self._ensure_session("LLM-Output")
        
        # Update current_product_id / current_product_name from output
        if "current_product_id" in output_data and output_data["current_product_id"]:
            session.current_product_id = output_data["current_product_id"]
        if "current_product_name" in output_data and output_data["current_product_name"]:
            session.current_product_name = output_data["current_product_name"]
        
        # Merge negotiated_products list
        incoming_products = output_data.get("negotiated_products", [])
        if not incoming_products:
            logger.info("[NegotiationEngine] No negotiated_products in output — skipping merge.")
            return
        
        for incoming in incoming_products:
            if isinstance(incoming, dict):
                pid = incoming.get("product_id")
                pname = incoming.get("product_name")
            elif hasattr(incoming, "product_id"):
                pid = incoming.product_id
                pname = getattr(incoming, "product_name", None)
                incoming = incoming.model_dump() if hasattr(incoming, "model_dump") else incoming.__dict__
            else:
                continue
                
            if not pid:
                logger.warning("[NegotiationEngine] Incoming negotiated product has no product_id — skipping.")
                continue
            
            # Try to find existing by ID first, then by name
            existing = self._find_negotiated_product(pid, pname)
            if existing:
                # Merge into existing — protect system-managed pricing fields
                self._merge_negotiated_product(existing, incoming)
                logger.info(f"[NegotiationEngine] Merged updates for product '{existing.product_id}'")
            else:
                # Fallback: if there's a current active product, LLM likely means that one
                # This prevents creating duplicate entries with hallucinated IDs/prices
                if session.current_product_id:
                    current_np = self._find_negotiated_product(session.current_product_id)
                    if current_np:
                        logger.warning(f"[NegotiationEngine] LLM returned unknown product_id '{pid}' — falling back to current product '{session.current_product_id}'")
                        self._merge_negotiated_product(current_np, incoming)
                        continue
                # Truly new product negotiation — add to list
                self._add_new_negotiated_product(incoming, pid)
                logger.info(f"[NegotiationEngine] Added new negotiated product '{pid}'")
        
        # Enforce product config for the current product
        if session.current_product_id:
            self._enforce_product_config(session.current_product_id)

    def _merge_negotiated_product(self, existing: NegotiatedProduct, incoming: dict) -> None:
        """Merge LLM output into an existing NegotiatedProduct, protecting system pricing."""
        # Fields the LLM should NOT overwrite (system-managed)
        protected_keys = {
            "active_base_price",
            "max_discount_percent",
        }
        
        existing_base = existing.active_base_price
        existing_max_disc = existing.max_discount_percent
        
        for k, v in incoming.items():
            if v is None:
                continue
            if k in protected_keys:
                logger.warning(f"[NegotiationEngine] Ignoring protected field '{k}' from LLM: {v}")
                continue
            if hasattr(existing, k):
                # Special handling for negotiation_attempts — monotonic increase
                if k == "negotiation_attempts":
                    current = existing.negotiation_attempts
                    try:
                        new_val = int(v)
                    except (ValueError, TypeError):
                        continue
                    is_new = incoming.get("negotiation_phase") == "initial"
                    if is_new:
                        existing.negotiation_attempts = new_val
                    elif new_val <= current:
                        existing.negotiation_attempts = current + 1
                    else:
                        existing.negotiation_attempts = new_val
                else:
                    setattr(existing, k, v)
        
        # Restore system-managed fields if they got cleared
        if existing_base is not None and (existing.active_base_price is None or existing.active_base_price == 0):
            existing.active_base_price = existing_base
        if existing_max_disc is not None and (existing.max_discount_percent is None or existing.max_discount_percent == 0):
            existing.max_discount_percent = existing_max_disc

    def _add_new_negotiated_product(self, data: dict, product_id: str) -> None:
        """Create a new NegotiatedProduct from LLM output and enrich with system config."""
        session = self.state.negotiation_state.negotiation_session
        
        # Ensure reasoning is present (required field)
        if "reasoning" not in data or not data["reasoning"]:
            data["reasoning"] = "New product negotiation started"
        
        try:
            np = NegotiatedProduct(**data)
        except Exception as e:
            logger.error(f"[NegotiationEngine] Failed to create NegotiatedProduct: {e}")
            return
        
        # Ensure negotiation is marked active for new products from LLM
        np.negotiation_active = True
        
        # Enrich with system pricing from product catalog
        products = self.state.bot_persona.company_products or []
        catalog_product = next((p for p in products if p.id == product_id), None)
        if catalog_product:
            if catalog_product.base_pricing is not None:
                np.active_base_price = catalog_product.base_pricing
            if catalog_product.max_discount_percent is not None:
                np.max_discount_percent = catalog_product.max_discount_percent
            elif self.state.negotiation_state.negotiation_config:
                np.max_discount_percent = self.state.negotiation_state.negotiation_config.max_discount_percent
            np.product_name = catalog_product.name
            np.product_id = catalog_product.id
        
        session.negotiated_products.append(np)

    ## Product config enforcement 
    def _enforce_product_config(self, product_id: str) -> None:
        """Look up product by ID and set active pricing variables for the matching NegotiatedProduct."""
        products = self.state.bot_persona.company_products or []
        product = next((p for p in products if p.id == product_id), None)
        
        if product:
            self._apply_product_to_state(product, source="EnforceConfig")
        else:
            logger.warning(f"[NegotiationEngine] Product ID '{product_id}' returned by LLM not found in persona!")

    def _apply_product_to_state(self, product, source: str) -> None:
        """Apply a product's system config to the negotiated_products list.
        
        Finds or creates the NegotiatedProduct entry for this product and
        sets system-managed pricing fields.
        """
        session = self._ensure_session(source)
        
        # Set current product on session level
        session.current_product_id = product.id
        session.current_product_name = product.name
        
        # Find or create NegotiatedProduct entry
        np = self._find_negotiated_product(product.id)
        if not np:
            np = NegotiatedProduct(
                product_id=product.id,
                product_name=product.name,
                negotiation_active=True,
                reasoning=f"Initialized by {source}"
            )
            session.negotiated_products.append(np)
            logger.info(f"[NegotiationEngine] Created NegotiatedProduct for '{product.name}' from {source}")
        
        # Store existing values for persistence check
        existing_discount = np.max_discount_percent
        is_new = existing_discount is None or existing_discount == 0
        
        # Always update base price
        if product.base_pricing is not None:
            np.active_base_price = product.base_pricing
        
        # Update max discount
        if product.max_discount_percent is not None:
            if is_new:
                np.max_discount_percent = product.max_discount_percent
                logger.info(f"[NegotiationEngine] Set max discount from product ({source}): {product.max_discount_percent}%")
            else:
                logger.info(f"[NegotiationEngine] PRESERVING existing discount ceiling {existing_discount}% ({source})")
                np.max_discount_percent = existing_discount
        else:
            if is_new:
                global_max = 5.0
                ns = self.state.negotiation_state
                if ns.negotiation_config and ns.negotiation_config.max_discount_percent is not None:
                    global_max = ns.negotiation_config.max_discount_percent
                np.max_discount_percent = global_max
                logger.info(f"[NegotiationEngine] Using global max discount ({source}): {global_max}%")
            else:
                logger.info(f"[NegotiationEngine] PRESERVING existing global discount ceiling: {existing_discount}% ({source})")
        
        # Ensure product name
        np.product_name = product.name
        np.product_id = product.id
        
        logger.info(f"[NegotiationEngine] Applied product '{product.name}' from {source}")