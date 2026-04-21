from emailbot.core.state import BotState, ObjectionState, ProbingOutput, ProbingContext


from emailbot.config.settings import logger


class ProbingEngineState:
    def __init__(self, state: BotState):
        self.state = state

    def update_probing_context(self, probing_details: ProbingOutput) -> tuple[ProbingContext, ObjectionState]:
        if not probing_details:
            return self.state.probing_context or ProbingContext(), self.state.objection_state or ObjectionState()

        logger.debug(f"###################ai probing_details#######################")
        logger.debug(f"Probing Details: {probing_details}")
        logger.debug(
            f"###########################BotState##############################"
        )
        logger.debug(f"Current Probing Context: {self.state.probing_context}")
        logger.debug(f"###############################################################")

        updated_detected_question_answer, total_score = self._process_email_probing(
            probing_details
        )

        threshold = self.state.bot_persona.probing_threshold or 0
        if total_score >= threshold:
            probing_details.can_show_cta = True
            probing_details.probing_completed = True

        if (
            self.state.objection_state.current_objection_count
            >= self.state.bot_persona.objection_count_limit
        ):
            probing_details.probing_completed = True
            probing_details.can_show_cta = True
            probing_details.is_objection = True
            logger.info("User has reached objection limit.")
            logger.info("Probing marked as completed, CTA can be shown.")

        # Update probing context
        probing_state = ProbingContext(
            detected_question_answer=updated_detected_question_answer,
            total_score=total_score,
            probing_completed=probing_details.probing_completed,
            can_show_cta=probing_details.can_show_cta,
            is_objection=probing_details.is_objection,
        )

        objection_state = self._update_objection_state(probing_details, probing_state)

        return probing_state, objection_state

    def _process_email_probing(
        self, probing_details: ProbingOutput
    ) -> tuple[list, float]:

        existing_question_answer = (
            self.state.probing_context.detected_question_answer
            if self.state.probing_context and self.state.probing_context.detected_question_answer
            else []
        )

        current_score = (
            self.state.probing_context.total_score
            if self.state.probing_context
            else 0.0
        )

        pairs = probing_details.detected_question_answer_pairs or []

        # ✅ FIXED MULTI-PAIR HANDLING
        if len(pairs) > 0:
            logger.info(f"[EMAIL] Processing {len(pairs)} probing question-answer pair(s)")

            new_entries: list = []
            added_score: float = 0.0

            for idx, pair in enumerate(pairs):
                if not pair:
                    continue

                score = getattr(pair, "score", 0.0) or 0.0
                is_answered = getattr(pair, "is_answered", False)

                entry = {
                    "question": getattr(pair, "question", ""),
                    "answer": getattr(pair, "answer", ""),
                    "score_to_add": score,
                    "is_answered": is_answered,
                }

                if is_answered:
                    new_entries.append(entry)
                    added_score += score
                    logger.info(f"[EMAIL]   Pair {idx + 1}: answered, score +{score}")
                else:
                    logger.info(f"[EMAIL]   Pair {idx + 1}: not answered, skipped")

            # ✅ CRITICAL FALLBACK FIX
            if added_score == 0.0 and probing_details.is_answered:
                logger.warning("[EMAIL] Pairs malformed/empty — falling back to score_to_add")
                added_score = probing_details.score_to_add or 0.0

                if probing_details.detected_question:
                    new_entries.append(
                        {
                            "question": probing_details.detected_question,
                            "answer": probing_details.detected_answer,
                            "score_to_add": probing_details.score_to_add,
                            "is_answered": probing_details.is_answered,
                        }
                    )

            updated = existing_question_answer + new_entries
            total_score = current_score + added_score

            logger.info(
                f"[EMAIL] Total score after this email: {total_score} "
                f"(+{added_score} from {len(new_entries)} answered pair(s))"
            )

            return updated, total_score

        # ---- FALLBACK (kept for backward compatibility) ----
        logger.info("[EMAIL] No multi-pair data; falling back to single-question processing")

        if probing_details.is_answered:
            updated = existing_question_answer + [
                {
                    "question": probing_details.detected_question,
                    "answer": probing_details.detected_answer,
                    "score_to_add": probing_details.score_to_add,
                    "is_answered": probing_details.is_answered,
                }
            ]
            total_score = current_score + (probing_details.score_to_add or 0.0)
        else:
            updated = existing_question_answer
            total_score = current_score

        return updated, total_score

    def _update_objection_state(
        self, probing_details: ProbingOutput, probing_state: ProbingContext
    ) -> ObjectionState:

        was_limit_already_reached = getattr(
            self.state.objection_state, "is_objection_limit_reached", False
        )
        # Get limit_reach_count (how many times limit has been hit and reset)
        limit_reach_count = getattr(
            self.state.objection_state, "limit_reach_count", 0
        )
        
        # RESET LOGIC: If limit WAS reached before, reset count on next message
        if was_limit_already_reached:
            logger.info('='*100)
            logger.info("OBJECTION RESET CYCLE: Limit was reached in previous message")
            logger.info(f"Previous limit_reach_count: {limit_reach_count}")
            
            # Increment limit_reach_count (track how many times we've reset)
            limit_reach_count += 1
            logger.info(f"Incrementing limit_reach_count to: {limit_reach_count}")
            
            # If limit_reach_count >= reset_count_limit, don't accept more objections
            if limit_reach_count >= self.state.bot_persona.reset_count_limit:
                logger.info(f"Limit reach count >= {self.state.bot_persona.reset_count_limit}: FREEZING OBJECTION COUNT")
                logger.info("New objections will NOT increment the count")
                current_objection_count = self.state.objection_state.current_objection_count
            else:
                logger.info(f"Resetting objection count to 0 for new cycle {limit_reach_count}")
                current_objection_count = 0
            
            is_objection_limit_reached = False
            probing_state.can_show_cta = False
            logger.info('='*100)
        else:
            # Only increment if limit_reach_count < reset_count_limit (allows full cycles)
            if limit_reach_count >= self.state.bot_persona.reset_count_limit:
                logger.info(f"Limit reach count is {limit_reach_count} - NOT incrementing objection count")
                logger.info("CTA is DISABLED - already reached limit twice before")
                current_objection_count = self.state.objection_state.current_objection_count
                is_objection_limit_reached = False
                probing_state.can_show_cta = False
            else:
                # Increment count if this is a new objection
                current_objection_count = self.state.objection_state.current_objection_count + (
                    1 if probing_details.is_objection else 0
                )
                # Check if we've NOW REACHED the limit
                is_objection_limit_reached = (
                    self.state.bot_persona.objection_count_limit <= current_objection_count
                )

        # UPDATE PROBING STATE BASED ON LIMIT STATUS
        # Rule: If is_objection_limit_reached=True → can_show_cta=FALSE, else → keep current value
        if is_objection_limit_reached:
            logger.info('='*100)
            logger.info(f"OBJECTION LIMIT REACHED: {current_objection_count}/{self.state.bot_persona.objection_count_limit}")
            logger.info("Setting CTA = FALSE (close conversation) and probing_completed = true")
            logger.info("Flag will stay true until next user message, then reset")
            logger.info('='*100)
            probing_state.can_show_cta = False
            probing_state.probing_completed = True
        
        # Check if probing was already completed BEFORE this call
        was_already_completed = (
            self.state.probing_context.probing_completed
            if self.state.probing_context
            else False
        )
        # If probing was already completed, maintain that state UNLESS frozen by limit_reach_count
        if was_already_completed and limit_reach_count < 2:
            probing_state.can_show_cta = True
            probing_state.probing_completed = True

        # Update objection state
        objection_state = ObjectionState(
            current_objection_count=current_objection_count,
            is_objection_limit_reached=is_objection_limit_reached,
            limit_reach_count=limit_reach_count,
            objection_analysis=getattr(probing_details, "objection_analysis", None),
        )

        return objection_state
