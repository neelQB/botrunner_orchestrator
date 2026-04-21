"""
Datetime tools for Agent-based booking workflows.
"""

import re
import pytz
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, time

from agents import function_tool, RunContextWrapper
from emailbot.core.state import BotState


from emailbot.config.settings import logger

from emailbot.prompts.lead_analysis import lead_analysis_prompt
from emailbot.route.route import RouterModel
from agents import ModelSettings
from emailbot.apis.calendly_api import calendly_available_slots_api

# =====================================================
# 1. CURRENT UTC TIME
# =====================================================

# @function_tool
# def utc_time_current(unused: Optional[str] = None) -> Dict[str, Any]:
#     """
#     Get current UTC datetime.

#     Returns:
#     - success
#     - current_time_utc (ISO 8601)
#     - current_time_readable
#     - unix_timestamp
#     """
#     try:
#         now = datetime.now(pytz.UTC)
#         return {
#             "success": True,
#             "current_time_utc": now.isoformat(),
#             "current_time_readable": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
#             "unix_timestamp": int(now.timestamp())
#         }
#     except Exception as e:
#         logger.error(f"utc_time_current error: {e}")
#         return {"success": False, "error": str(e)}


# =====================================================
# 2. UNIFIED DATETIME PROCESSING TOOL (Combines parse, validate, convert)
# =====================================================


def _parse_datetime_expression(relative_str: str, timezone: str) -> Dict:
    """
    Internal helper to parse relative datetime expressions.
    This is the parsing logic extracted from the original parse_relative_datetime.

    Args:
        relative_str: Relative time expression
        timezone: Timezone name

    Returns:
        Dictionary with parsed datetime or error
    """
    try:
        import datetime as dt

        tz = pytz.timezone(timezone)
        now = dt.datetime.now(tz)

        relative_lower = relative_str.lower().strip()
        relative_lower_no_comma = relative_lower.replace(",", " ")

        # Extract time from the string if present
        time_match = re.search(
            r"(\d{1,2})[:.]?(\d{2})?\s*(am|pm)", relative_lower, re.IGNORECASE
        )

        extracted_hour = None
        extracted_minute = None
        has_explicit_time = False

        if time_match:
            has_explicit_time = True
            extracted_hour = int(time_match.group(1))
            extracted_minute = int(time_match.group(2)) if time_match.group(2) else 0
            am_pm = time_match.group(3).lower()

            if am_pm == "pm" and extracted_hour < 12:
                extracted_hour += 12
            elif am_pm == "am" and extracted_hour == 12:
                extracted_hour = 0
        else:
            time_match_24 = re.search(r"(\d{1,2}):(\d{2})", relative_lower)
            if time_match_24:
                hour = int(time_match_24.group(1))
                if 0 <= hour <= 23:
                    has_explicit_time = True
                    extracted_hour = hour
                    extracted_minute = int(time_match_24.group(2))

        # Handle 'in X minutes/hours/days'
        if "in " in relative_lower:
            match = re.search(r"in\s+(\d+)\s+(minute|hour|day|week)s?", relative_lower)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == "minute":
                    target_date = now + dt.timedelta(minutes=amount)
                elif unit == "hour":
                    target_date = now + dt.timedelta(hours=amount)
                elif unit == "day":
                    target_date = now + dt.timedelta(days=amount)
                elif unit == "week":
                    target_date = now + dt.timedelta(weeks=amount)
                else:
                    target_date = now

                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"in {amount} {unit}{'s' if amount > 1 else ''}",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": False,
                }

        # Handle 'tomorrow'
        if "tomorrow" in relative_lower:
            target_date = now + dt.timedelta(days=1)
            if has_explicit_time:
                target_date = target_date.replace(
                    hour=extracted_hour,
                    minute=extracted_minute,
                    second=0,
                    microsecond=0,
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"tomorrow at {extracted_hour}:{extracted_minute:02d}",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": False,
                }
            else:
                target_date = target_date.replace(
                    hour=10, minute=0, second=0, microsecond=0
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": "tomorrow (default 10:00 AM)",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": True,
                }

        # Handle 'today'
        if "today" in relative_lower:
            if has_explicit_time:
                target_date = now.replace(
                    hour=extracted_hour,
                    minute=extracted_minute,
                    second=0,
                    microsecond=0,
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"today at {extracted_hour}:{extracted_minute:02d}",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": False,
                }
            else:
                target_date = now.replace(hour=10, minute=0, second=0, microsecond=0)
                return {
                    "date": now.strftime("%Y-%m-%d"),
                    "time": "10:00",
                    "interpreted_as": "today (default 10:00 AM)",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": True,
                }

        # Handle 'next week'
        if "next week" in relative_lower:
            target_date = now + dt.timedelta(days=7)
            target_date = target_date.replace(
                hour=10, minute=0, second=0, microsecond=0
            )
            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "time": target_date.strftime("%H:%M"),
                "interpreted_as": "next week (default 10:00 AM)",
                "full_datetime": target_date.isoformat(),
                "time_defaulted": True,
            }

        # Handle time of day references
        time_of_day_map = {
            "morning": (10, 0),
            "noon": (12, 0),
            "afternoon": (14, 0),
            "evening": (18, 0),
            "night": (20, 0),
            "lunch": (14, 0),
        }

        for time_word, (hour, minute) in time_of_day_map.items():
            if time_word in relative_lower:
                target_date = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if target_date < now:
                    target_date += dt.timedelta(days=1)
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": time_word,
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": False,
                }

        # Handle day names (next Monday, etc.)
        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for i, day in enumerate(days):
            if day in relative_lower:
                current_weekday = now.weekday()
                days_ahead = i - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + dt.timedelta(days=days_ahead)

                if has_explicit_time:
                    target_date = target_date.replace(
                        hour=extracted_hour,
                        minute=extracted_minute,
                        second=0,
                        microsecond=0,
                    )
                    return {
                        "date": target_date.strftime("%Y-%m-%d"),
                        "time": target_date.strftime("%H:%M"),
                        "interpreted_as": f"next {day} at {extracted_hour}:{extracted_minute:02d}",
                        "full_datetime": target_date.isoformat(),
                        "time_defaulted": False,
                    }
                else:
                    target_date = target_date.replace(
                        hour=10, minute=0, second=0, microsecond=0
                    )
                    return {
                        "date": target_date.strftime("%Y-%m-%d"),
                        "time": target_date.strftime("%H:%M"),
                        "interpreted_as": f"next {day} (default 10:00 AM)",
                        "full_datetime": target_date.isoformat(),
                        "time_defaulted": True,
                    }

        # Handle explicit dates
        date_patterns = [
            r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?",
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?",
            r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})",
            r"(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})",
        ]

        month_map = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        for pattern in date_patterns:
            match = re.search(pattern, relative_lower_no_comma)
            if match:
                groups = match.groups()
                target_date = None
                year = None
                month = None
                day = None

                if len(groups) == 3 and groups[1] in month_map:
                    day = int(groups[0])
                    month = month_map[groups[1]]
                    year = int(groups[2]) if groups[2] else None
                elif len(groups) == 3 and groups[0] in month_map:
                    month = month_map[groups[0]]
                    day = int(groups[1])
                    year = int(groups[2]) if groups[2] else None
                elif len(groups) == 3 and groups[0].isdigit() and len(groups[0]) <= 2:
                    day = int(groups[0])
                    month = int(groups[1])
                    year = int(groups[2])
                elif len(groups) == 3 and len(groups[0]) == 4:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])

                if year is None:
                    year = now.year
                    if month < now.month or (month == now.month and day < now.day):
                        year = now.year + 1

                if day and month and year:
                    try:
                        target_date = now.replace(
                            year=year,
                            month=month,
                            day=day,
                            hour=10,
                            minute=0,
                            second=0,
                            microsecond=0,
                        )
                    except ValueError as e:
                        return {"parse_error": f"Invalid date: {e}"}

                if target_date:
                    if has_explicit_time:
                        target_date = target_date.replace(
                            hour=extracted_hour, minute=extracted_minute
                        )
                        return {
                            "date": target_date.strftime("%Y-%m-%d"),
                            "time": target_date.strftime("%H:%M"),
                            "interpreted_as": f"{target_date.strftime('%B %d, %Y')} at {extracted_hour}:{extracted_minute:02d}",
                            "full_datetime": target_date.isoformat(),
                            "time_defaulted": False,
                        }
                    else:
                        return {
                            "date": target_date.strftime("%Y-%m-%d"),
                            "time": "10:00",
                            "interpreted_as": f"{target_date.strftime('%B %d, %Y')} (default 10:00 AM)",
                            "full_datetime": target_date.isoformat(),
                            "time_defaulted": True,
                        }

        return {"parse_error": f"Could not parse datetime expression: {relative_str}"}
    except Exception as e:
        logger.error(f"Error parsing datetime: {e}")
        return {"parse_error": str(e)}


def _validate_booking_datetime(
    date_str: str,
    time_str: str,
    timezone: str,
    working_hours: Optional[List[dict]] = None,
    holidays: Optional[List[dict]] = None,
) -> Dict:
    """
    Internal helper to validate booking datetime against business rules.

    Rules:
    - Not in the past
    - Not weekend (or Holiday if defined in persona working_hours)
    - Working hours: either persona-defined or default 10:00–23:00
    - Not more than 6 months in future

    When `working_hours` is provided (list of objects with keys: day, type, start_time, end_time),
    validation will use those values for the specific day-of-week. Otherwise, falls back to
    the default rules used historically.

    Returns:
        Dictionary with validation results
    """
    logger.info("_validate_booking_datetime call")
    logger.info("holidays")
    logger.info(holidays)
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        hour, minute = map(int, time_str.split(":"))

        booking_dt = tz.localize(datetime.combine(date_obj, time(hour, minute)))

        is_past = booking_dt < now
        is_too_far = date_obj > (now.date() + timedelta(days=180))

        # Default values
        is_weekend = date_obj.weekday() >= 5
        is_outside_working_hours = False
        is_holiday = False
        used_working_hours = None

        day_name = date_obj.strftime("%A")

        # If persona working_hours provided, try to use it for validation (supports both dicts and Pydantic models)
        if working_hours:
            try:
                match = None
                for w in working_hours:
                    w_day = getattr(w, "day", None) or (
                        w.get("day") if isinstance(w, dict) else None
                    )
                    if w_day and w_day == day_name:
                        match = w
                        break

                if match:
                    w_type = getattr(match, "type", None) or (
                        match.get("type") if isinstance(match, dict) else None
                    )
                    start_time = getattr(match, "start_time", None) or (
                        match.get("start_time") if isinstance(match, dict) else None
                    )
                    end_time = getattr(match, "end_time", None) or (
                        match.get("end_time") if isinstance(match, dict) else None
                    )

                    used_working_hours = {
                        "day": day_name,
                        "type": w_type,
                        "start_time": start_time,
                        "end_time": end_time,
                    }

                    if w_type and str(w_type).lower() == "holiday":
                        is_holiday = True
                    elif (
                        w_type
                        and str(w_type).lower() == "working"
                        and start_time
                        and end_time
                    ):
                        # Parse HH:MM
                        try:
                            sh, sm = map(int, start_time.split(":"))
                            eh, em = map(int, end_time.split(":"))
                            start_minutes = sh * 60 + sm
                            end_minutes = eh * 60 + em
                            booking_minutes = hour * 60 + minute

                            if not (start_minutes <= booking_minutes <= end_minutes):
                                is_outside_working_hours = True
                        except Exception:
                            # Malformed persona times - fallback to default
                            logger.warning(
                                "Malformed working_hours times; falling back to defaults"
                            )
                    else:
                        # Unknown type - fallback to default weekday/weekend behaviour
                        pass
            except Exception as e:
                logger.error(f"Error processing working_hours: {e}")

        # If no persona working hours or not used, apply defaults
        if not working_hours or used_working_hours is None:
            is_weekend = date_obj.weekday() >= 5
            # default working hours are 10:00 - 23:00
            is_outside_working_hours = not (10 <= hour <= 23)

        # Check for specific holidays
        if holidays:
            logger.info("------------------------------")
            logger.info(date_str)
            for h in holidays:
                h_date = getattr(h, "date", None) or (
                    h.get("date") if isinstance(h, dict) else None
                )
                holiday_name = getattr(h, "name", None) or (
                    h.get("name") if isinstance(h, dict) else None
                )
                logger.info(holiday_name)
                logger.info(h_date)
                if h_date == date_str:
                    is_holiday = True
                    day_name = holiday_name
                    logger.info("is_holiday")
                    logger.info(is_holiday)
                    break

        # Final validity
        is_valid = not any(
            [is_past, is_weekend, is_outside_working_hours, is_too_far, is_holiday]
        )

        # Build validation message for failures
        validation_message = None
        if not is_valid:
            if is_holiday:
                validation_message = f"We do not schedule demos on {day_name} (marked as a holiday). Please choose another date."
            elif is_past:
                validation_message = "The selected date/time is in the past. Please choose a future date and time."
            elif is_outside_working_hours:
                if (
                    used_working_hours
                    and used_working_hours.get("start_time")
                    and used_working_hours.get("end_time")
                ):
                    validation_message = f"Our working hours on {day_name} are between {used_working_hours['start_time']} and {used_working_hours['end_time']}. Please choose a time within these hours."
                else:
                    validation_message = "Our working hours are between 10:00 AM and 11:00 PM. Please choose a time within these hours."
            elif is_too_far:
                validation_message = "The date is more than 6 months in the future. Please choose an earlier date."

        return {
            "is_valid": is_valid,
            "is_past": is_past,
            "is_weekend": is_weekend,
            "is_outside_working_hours": is_outside_working_hours,
            "is_too_far": is_too_far,
            "is_holiday": is_holiday,
            "day_of_week": day_name,
            "current_time": now.strftime("%Y-%m-%d %H:%M"),
            "validation_message": validation_message,
            "used_working_hours": used_working_hours,
        }

    except Exception as e:
        logger.error(f"validate_datetime error: {e}")
        return {"is_valid": False, "validation_error": str(e)}


def _convert_to_utc(date_str: str, time_str: str, timezone: str) -> Dict:
    """
    Internal helper to convert local date and time to UTC ISO format.

    Returns:
        Dictionary with UTC conversion results
    """
    try:
        tz = pytz.timezone(timezone)
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        localized_dt = tz.localize(dt)
        utc_dt = localized_dt.astimezone(pytz.UTC)

        return {
            "success": True,
            "utc_time_iso": utc_dt.isoformat(),
            "utc_time_readable": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "local_time": localized_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
            "local_time_readable": localized_dt.strftime("%B %d, %Y at %I:%M %p %Z"),
        }
    except Exception as e:
        logger.error(f"convert_to_utc error: {e}")
        return {"success": False, "conversion_error": str(e)}


@function_tool
def process_booking_datetime(
    ctx: RunContextWrapper[BotState], datetime_expression: str, timezone: str
) -> Dict[str, Any]:
    """
    UNIFIED DATETIME PROCESSING TOOL for demo booking workflow.

    This tool combines parsing, validation, and UTC conversion into a single call.
    It handles all datetime processing needs for booking, rescheduling operations.

    WHEN TO USE:
    - User provides any date/time expression (relative or absolute)
    - For new bookings or rescheduling
    - Examples: "tomorrow 3pm", "next Monday at 2:30 PM", "December 26 at 4:00 PM", "in 2 hours"

    WHAT IT DOES (in sequence):
    1. PARSES the datetime expression into structured date and time
    2. VALIDATES against business rules (weekday, working hours 10AM-11PM, not past, within 6 months)
    3. CONVERTS to UTC ISO format (only if validation passes)
    4. UPDATES state with the collected date/time fields

    Args:
        datetime_expression: Natural language datetime (e.g., "tomorrow 3pm", "8th December at 2:30 PM")
        timezone: User's timezone (e.g., "Asia/Kolkata", "America/New_York")

    Returns:
        Dictionary with complete processing results:
        - success: true/false indicating if all steps completed successfully
        - parsed: Parsing results (date, time, interpreted_as, time_defaulted)
        - validation: Validation results (is_valid, is_weekend, is_past, etc.)
        - utc_conversion: UTC conversion results (utc_time_iso, local_time, etc.)
        - error: Error message if any step failed
        - next_action: Suggested next action based on results

    RESPONSE HANDLING:
    - If time_defaulted=true: Ask user to specify a time
    - If validation fails: Show validation_message and ask for correction
    - If success=true: Use utc_time_iso for Calendly availability check
    """
    logger.info(
        f"***** UNIFIED DATETIME PROCESSING: expression='{datetime_expression}', timezone='{timezone}' *****"
    )

    result = {
        "success": False,
        "parsed": None,
        "validation": None,
        "utc_conversion": None,
        "error": None,
        "next_action": None,
    }

    try:
        # STEP 1: Parse the datetime expression
        logger.info(f"Step 1: Parsing datetime expression: {datetime_expression}")
        parsed = _parse_datetime_expression(datetime_expression, timezone)

        if "parse_error" in parsed:
            result["error"] = parsed["parse_error"]
            result["next_action"] = "ask_clarification"
            result["message"] = (
                f"Could not understand the date/time. Please provide a clear date and time, like 'tomorrow at 3 PM' or 'December 26 at 4:00 PM'."
            )
            logger.warning(f"Parsing failed: {parsed['parse_error']}")
            return result

        result["parsed"] = parsed
        logger.info(
            f"Parsed result: date={parsed.get('date')}, time={parsed.get('time')}, time_defaulted={parsed.get('time_defaulted')}"
        )

        # Resolve working_hours and holidays from bot_persona.
        # Always load persona config — this tool is only called during booking flows
        # so we should never skip holiday/working_hours validation based on agent name.
        working_hours = None
        holidays = None
        try:
            if ctx and ctx.context and getattr(ctx.context, "bot_persona", None):
                working_hours = getattr(
                    ctx.context.bot_persona, "working_hours", None
                )
                holidays = getattr(ctx.context.bot_persona, "holiday", None)
                logger.debug(
                    f"Loaded from bot_persona — working_hours={bool(working_hours)}, holidays={holidays}"
                )
        except Exception as e:
            logger.debug(f"Could not load persona working hours/holidays: {e}")

        # Check if time was defaulted (user only provided date)
        if parsed.get("time_defaulted", False):
            # PRE-VALIDATE the date before asking for a time.
            # Use a dummy time (10:00) to check date-level rules: weekend, holiday,
            # and too-far-in-future. We deliberately skip is_past here because
            # that depends on the actual time the user will provide.
            date_str_pre = parsed["date"]
            pre_validation = _validate_booking_datetime(
                date_str_pre, "10:00", timezone, working_hours, holidays
            )
            if (
                pre_validation.get("is_weekend")
                or pre_validation.get("is_holiday")
                or pre_validation.get("is_too_far")
            ):
                result["success"] = False
                result["next_action"] = "ask_correction"
                result["validation"] = pre_validation
                result["message"] = pre_validation.get(
                    "validation_message",
                    "The selected date is not a valid working day. Please choose a weekday.",
                )
                logger.warning(
                    f"Date pre-validation failed (asked before time): {pre_validation}"
                )
                return result

            result["success"] = False
            result["next_action"] = "ask_time"
            result["message"] = (
                f"I understood the date as {parsed.get('interpreted_as')}. What time works best for you? Our working hours are between 10 AM and 7 PM."
            )
            logger.info("Time was defaulted - asking user for specific time")
            return result

        date_str = parsed["date"]
        time_str = parsed["time"]

        # STEP 2: Validate against business rules
        logger.info(f"Step 2: Validating datetime: date={date_str}, time={time_str}")
        validation = _validate_booking_datetime(
            date_str, time_str, timezone, working_hours, holidays
        )
        result["validation"] = validation

        if not validation.get("is_valid", False):
            result["success"] = False
            result["next_action"] = "ask_correction"
            result["message"] = validation.get(
                "validation_message",
                "The selected date/time is not valid. Please choose another.",
            )
            logger.warning(f"Validation failed: {validation}")
            return result

        logger.info(f"Validation passed: {validation}")

        # STEP 3: Convert to UTC
        logger.info(
            f"Step 3: Converting to UTC: date={date_str}, time={time_str}, tz={timezone}"
        )
        utc_conversion = _convert_to_utc(date_str, time_str, timezone)
        result["utc_conversion"] = utc_conversion

        if not utc_conversion.get("success", False):
            result["error"] = utc_conversion.get(
                "conversion_error", "UTC conversion failed"
            )
            result["next_action"] = "ask_correction"
            result["message"] = (
                "There was an issue processing the time. Please try again with a different format."
            )
            logger.error(f"UTC conversion failed: {utc_conversion}")
            return result

        logger.info(f"UTC conversion successful: {utc_conversion.get('utc_time_iso')}")

        # STEP 4: Update state with collected fields
        if ctx and ctx.context:
            if not ctx.context.user_context.collected_fields:
                ctx.context.user_context.collected_fields = {}
            ctx.context.user_context.collected_fields["date"] = date_str
            ctx.context.user_context.collected_fields["time"] = utc_conversion[
                "utc_time_iso"
            ]
            ctx.context.user_context.timezone = timezone
            logger.info(
                f"State updated: date={date_str}, time={utc_conversion['utc_time_iso']}"
            )

        # All steps successful
        result["success"] = True
        result["next_action"] = "check_calendly"
        result["message"] = (
            f"Date/time validated: {parsed.get('interpreted_as')}. Ready to check availability."
        )

        # Add convenient summary fields
        result["date"] = date_str
        result["time"] = time_str
        result["utc_time_iso"] = utc_conversion["utc_time_iso"]
        result["local_time_readable"] = utc_conversion["local_time_readable"]
        result["day_of_week"] = validation.get("day_of_week")

        logger.info(
            f"***** UNIFIED DATETIME PROCESSING COMPLETE: success=True, utc={utc_conversion['utc_time_iso']} *****"
        )
        return result

    except Exception as e:
        logger.error(f"Unexpected error in process_booking_datetime: {e}")
        result["error"] = str(e)
        result["next_action"] = "ask_correction"
        result["message"] = (
            "There was an unexpected error. Please try providing the date and time in a different format."
        )
        return result


# =====================================================
# LEGACY TOOLS (kept for backward compatibility but DEPRECATED)
# Use process_booking_datetime instead for new implementations
# =====================================================


@function_tool
def parse_relative_datetime(relative_str: str, timezone: str) -> Dict:
    """
    [DEPRECATED] Use process_booking_datetime instead.
    Parse relative datetime expressions like 'tomorrow', 'in 3 hours', 'next Monday', '8th December at 2:30 PM'
    ALWAYS returns time in HH:MM format
    Defaults to 10:00 AM if only date is provided

    Args:
        relative_str: Relative time expression
        timezone: Timezone name

    Returns:
        Dictionary with parsed datetime (always includes 'time' field in HH:MM format)
    """
    logger.warning(
        "parse_relative_datetime is DEPRECATED. Use process_booking_datetime instead."
    )
    result = _parse_datetime_expression(relative_str, timezone)
    if "parse_error" in result:
        return {"error": result["parse_error"]}
    return result


# Keep the original parse_relative_datetime implementation for reference
def _legacy_parse_relative_datetime(relative_str: str, timezone: str) -> Dict:
    """Legacy implementation kept for reference."""
    try:
        import datetime as dt

        tz = pytz.timezone(timezone)
        now = dt.datetime.now(tz)

        relative_lower = relative_str.lower().strip()
        # Remove commas for easier parsing
        relative_lower_no_comma = relative_lower.replace(",", " ")

        # FIRST: Extract time from the string if present (do this early!)
        # Pattern 1: Time with AM/PM (most specific) - e.g., "2:30 PM", "2:30PM", "2PM"
        time_match = re.search(
            r"(\d{1,2})[:.]?(\d{2})?\s*(am|pm)", relative_lower, re.IGNORECASE
        )

        extracted_hour = None
        extracted_minute = None
        has_explicit_time = False

        if time_match:
            has_explicit_time = True
            extracted_hour = int(time_match.group(1))
            extracted_minute = int(time_match.group(2)) if time_match.group(2) else 0
            am_pm = time_match.group(3).lower()

            # Convert to 24-hour format
            if am_pm == "pm" and extracted_hour < 12:
                extracted_hour += 12
            elif am_pm == "am" and extracted_hour == 12:
                extracted_hour = 0
        else:
            # Pattern 2: 24-hour time without AM/PM - e.g., "14:30", "09:00"
            time_match_24 = re.search(r"(\d{1,2}):(\d{2})", relative_lower)
            if time_match_24:
                hour = int(time_match_24.group(1))
                if 0 <= hour <= 23:  # Valid 24-hour format
                    has_explicit_time = True
                    extracted_hour = hour
                    extracted_minute = int(time_match_24.group(2))

        # Handle 'in X minutes/hours/days'
        if "in " in relative_lower:
            match = re.search(r"in\s+(\d+)\s+(minute|hour|day|week)s?", relative_lower)
            if match:
                amount = int(match.group(1))
                unit = match.group(2)

                if unit == "minute":
                    target_date = now + datetime.timedelta(minutes=amount)
                elif unit == "hour":
                    target_date = now + datetime.timedelta(hours=amount)
                elif unit == "day":
                    target_date = now + datetime.timedelta(days=amount)
                elif unit == "week":
                    target_date = now + datetime.timedelta(weeks=amount)
                else:
                    target_date = now

                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"in {amount} {unit}{'s' if amount > 1 else ''}",
                    "full_datetime": target_date.isoformat(),
                }

        # Handle 'tomorrow'
        if "tomorrow" in relative_lower:
            target_date = now + datetime.timedelta(days=1)
            if has_explicit_time:
                target_date = target_date.replace(
                    hour=extracted_hour,
                    minute=extracted_minute,
                    second=0,
                    microsecond=0,
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"tomorrow at {extracted_hour}:{extracted_minute:02d}",
                    "full_datetime": target_date.isoformat(),
                }
            else:
                target_date = target_date.replace(
                    hour=10, minute=0, second=0, microsecond=0
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": "tomorrow (default 10:00 AM)",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": True,
                }

        # Handle 'today'
        if "today" in relative_lower:
            if has_explicit_time:
                target_date = now.replace(
                    hour=extracted_hour,
                    minute=extracted_minute,
                    second=0,
                    microsecond=0,
                )
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": f"today at {extracted_hour}:{extracted_minute:02d}",
                    "full_datetime": target_date.isoformat(),
                }
            else:
                target_date = now.replace(hour=10, minute=0, second=0, microsecond=0)
                return {
                    "date": now.strftime("%Y-%m-%d"),
                    "time": "10:00",
                    "interpreted_as": "today (default 10:00 AM)",
                    "full_datetime": target_date.isoformat(),
                    "time_defaulted": True,
                }

        # Handle 'next week'
        if "next week" in relative_lower:
            target_date = now + datetime.timedelta(days=7)
            target_date = target_date.replace(
                hour=10, minute=0, second=0, microsecond=0
            )
            return {
                "date": target_date.strftime("%Y-%m-%d"),
                "time": target_date.strftime("%H:%M"),
                "interpreted_as": "next week (default 10:00 AM)",
                "full_datetime": target_date.isoformat(),
                "time_defaulted": True,
            }

        # Handle time of day references
        time_of_day_map = {
            "morning": (10, 0),
            "noon": (12, 0),
            "afternoon": (14, 0),
            "evening": (18, 0),
            "night": (20, 0),
            "lunch": (14, 0),
        }

        for time_word, (hour, minute) in time_of_day_map.items():
            if time_word in relative_lower:
                target_date = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
                if target_date < now:
                    target_date += datetime.timedelta(days=1)
                return {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "time": target_date.strftime("%H:%M"),
                    "interpreted_as": time_word,
                    "full_datetime": target_date.isoformat(),
                }

        # Handle day names (next Monday, etc.)
        days = [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
        for i, day in enumerate(days):
            if day in relative_lower:
                current_weekday = now.weekday()
                days_ahead = i - current_weekday
                if days_ahead <= 0:
                    days_ahead += 7
                target_date = now + datetime.timedelta(days=days_ahead)

                if has_explicit_time:
                    target_date = target_date.replace(
                        hour=extracted_hour,
                        minute=extracted_minute,
                        second=0,
                        microsecond=0,
                    )
                    return {
                        "date": target_date.strftime("%Y-%m-%d"),
                        "time": target_date.strftime("%H:%M"),
                        "interpreted_as": f"next {day} at {extracted_hour}:{extracted_minute:02d}",
                        "full_datetime": target_date.isoformat(),
                    }
                else:
                    target_date = target_date.replace(
                        hour=10, minute=0, second=0, microsecond=0
                    )
                    return {
                        "date": target_date.strftime("%Y-%m-%d"),
                        "time": target_date.strftime("%H:%M"),
                        "interpreted_as": f"next {day} (default 10:00 AM)",
                        "full_datetime": target_date.isoformat(),
                        "time_defaulted": True,
                    }

        # Handle explicit dates (e.g., "9th dec", "December 9", "12/9", "9-12-2025", "8th December at 2:30 PM")
        date_patterns = [
            # "9th dec 2026", "9 december 2025", "8th December, 2026" (with optional comma and year)
            r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?",
            # "dec 9", "december 9th 2025", "January 12th, 2026"
            r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?",
            # "12/9/2025", "9-12-2025", "12.9.2025"
            r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})",
            # "2025-12-09", "2025.12.09"
            r"(\d{4})[/.\-](\d{1,2})[/.\-](\d{1,2})",
        ]

        month_map = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
            "january": 1,
            "february": 2,
            "march": 3,
            "april": 4,
            "may": 5,
            "june": 6,
            "july": 7,
            "august": 8,
            "september": 9,
            "october": 10,
            "november": 11,
            "december": 12,
        }

        for pattern in date_patterns:
            match = re.search(pattern, relative_lower_no_comma)
            if match:
                groups = match.groups()
                target_date = None
                year = None
                month = None
                day = None

                # Pattern 1: "9th dec" or "9 december 2025" or "8th December"
                if len(groups) == 3 and groups[1] in month_map:
                    day = int(groups[0])
                    month = month_map[groups[1]]
                    year = int(groups[2]) if groups[2] else None

                # Pattern 2: "dec 9" or "december 9th 2025" or "January 12th 2026"
                elif len(groups) == 3 and groups[0] in month_map:
                    month = month_map[groups[0]]
                    day = int(groups[1])
                    year = int(groups[2]) if groups[2] else None

                # Pattern 3: "12/9/2025" or "9-12-2025" (DD/MM/YYYY format)
                elif len(groups) == 3 and groups[0].isdigit() and len(groups[0]) <= 2:
                    day = int(groups[0])
                    month = int(groups[1])
                    year = int(groups[2])

                # Pattern 4: "2025-12-09" (ISO format - YYYY-MM-DD)
                elif len(groups) == 3 and len(groups[0]) == 4:
                    year = int(groups[0])
                    month = int(groups[1])
                    day = int(groups[2])

                # Apply year logic: if no year provided or month is in the past, use next occurrence
                if year is None:
                    year = now.year
                    # If the month is before current month, or same month but day has passed, use next year
                    if month < now.month or (month == now.month and day < now.day):
                        year = now.year + 1

                if day and month and year:
                    try:
                        target_date = now.replace(
                            year=year,
                            month=month,
                            day=day,
                            hour=10,
                            minute=0,
                            second=0,
                            microsecond=0,
                        )
                    except ValueError as e:
                        return {"error": f"Invalid date: {e}"}

                if target_date:
                    # Use extracted time if available
                    if has_explicit_time:
                        target_date = target_date.replace(
                            hour=extracted_hour, minute=extracted_minute
                        )
                        return {
                            "date": target_date.strftime("%Y-%m-%d"),
                            "time": target_date.strftime("%H:%M"),
                            "interpreted_as": f"{target_date.strftime('%B %d, %Y')} at {extracted_hour}:{extracted_minute:02d}",
                            "full_datetime": target_date.isoformat(),
                        }
                    else:
                        # No time mentioned, default to 10 AM and set flag
                        return {
                            "date": target_date.strftime("%Y-%m-%d"),
                            "time": "10:00",
                            "interpreted_as": f"{target_date.strftime('%B %d, %Y')} (default 10:00 AM)",
                            "full_datetime": target_date.isoformat(),
                            "time_defaulted": True,
                        }

        return {"error": f"Could not parse relative datetime: {relative_str}"}
    except Exception as e:
        logger.error(f"Error parsing relative datetime: {e}")
        return {"error": str(e)}


def extract_slots(calendly_response):
    slots = calendly_response.get("slots", [])

    return [
        {"start_time_utc": slot.get("start_time_utc"), "status": slot.get("status")}
        for slot in slots
        if slot.get("start_time_utc")  # only include valid entries
    ]


@function_tool
def parse_relative_time(relative_str: str, timezone: str) -> Dict[str, Any]:
    """
    Parse relative datetime expressions like:
    - tomorrow
    - today at 3 PM
    - in 2 hours
    - next monday
    - 8th December at 2:30 PM

    Defaults to 10:00 AM if date has no explicit time.

    Returns:
    - date (YYYY-MM-DD)
    - time (HH:MM)
    - full_datetime (ISO)
    - interpreted_as
    - time_defaulted (optional)
    """
    logger.info(
        f"************** {relative_str} in timezone: {timezone}****************"
    )
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        text = relative_str.lower().strip()

        # --- Extract explicit time (AM/PM or 24h)
        hour = minute = None
        has_time = False

        match_ampm = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", text)
        match_24 = re.search(r"\b(\d{1,2}):(\d{2})\b", text)

        if match_ampm:
            hour = int(match_ampm.group(1))
            minute = int(match_ampm.group(2) or 0)
            if match_ampm.group(3) == "pm" and hour < 12:
                hour += 12
            if match_ampm.group(3) == "am" and hour == 12:
                hour = 0
            has_time = True

        elif match_24:
            hour = int(match_24.group(1))
            minute = int(match_24.group(2))
            has_time = True

        # --- Handle "in X hours / days"
        rel_match = re.search(r"in\s+(\d+)\s+(minute|hour|day|week)s?", text)
        if rel_match:
            amount = int(rel_match.group(1))
            unit = rel_match.group(2)
            delta = timedelta(**{unit + "s": amount})
            target = now + delta
            return {
                "date": target.strftime("%Y-%m-%d"),
                "time": target.strftime("%H:%M"),
                "full_datetime": target.isoformat(),
                "interpreted_as": f"in {amount} {unit}(s)",
            }

        # --- Tomorrow / Today
        if "tomorrow" in text:
            target = now + timedelta(days=1)
        elif "today" in text:
            target = now
        else:
            target = None

        if target:
            if has_time:
                target = target.replace(hour=hour, minute=minute, second=0)
            else:
                target = target.replace(hour=10, minute=0, second=0)
            return {
                "date": target.strftime("%Y-%m-%d"),
                "time": target.strftime("%H:%M"),
                "full_datetime": target.isoformat(),
                "interpreted_as": relative_str,
                "time_defaulted": not has_time,
            }

        return {"error": f"Could not parse relative time: {relative_str}"}

    except Exception as e:
        logger.error(f"parse_relative_time error: {e}")
        return {"error": str(e)}


# =====================================================
# 3. VALIDATE BOOKING DATETIME (Business Rules)
# =====================================================


@function_tool
def validate_datetime(date: str, time_str: str, timezone: str) -> Dict[str, Any]:
    """
    Validate booking datetime.

    Rules:
    - Not in the past
    - Not weekend
    - Working hours: 10:00–23:00
    - Not more than 6 months in future
    """
    logger.info(
        f"***********************Validating datetime: date={date}, time={time_str}, timezone={timezone}***************"
    )
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)

        date_obj = datetime.strptime(date, "%Y-%m-%d").date()
        hour, minute = map(int, time_str.split(":"))

        booking_dt = tz.localize(datetime.combine(date_obj, time(hour, minute)))

        is_past = booking_dt < now
        is_weekend = date_obj.weekday() >= 5
        is_outside_working_hours = not (10 <= hour <= 23)
        is_too_far = date_obj > (now.date() + timedelta(days=180))

        return {
            "is_valid": not any(
                [is_past, is_weekend, is_outside_working_hours, is_too_far]
            ),
            "is_past": is_past,
            "is_weekend": is_weekend,
            "is_outside_working_hours": is_outside_working_hours,
            "is_too_far": is_too_far,
            "day_of_week": date_obj.strftime("%A"),
            "current_time": now.strftime("%Y-%m-%d %H:%M"),
        }

    except Exception as e:
        logger.error(f"validate_datetime error: {e}")
        return {"is_valid": False, "error": str(e)}


# =====================================================
# 4. VALIDATE / NORMALIZE UTC TIME STRING
# =====================================================

# @function_tool
# def validate_utc_time(dt_str: Optional[str]) -> Dict[str, Any]:
#     """
#     Validate and normalize datetime string to UTC.

#     Accepts:
#     - ISO 8601
#     - 'YYYY-MM-DD HH:MM[:SS]'
#     - trailing Z

#     Naive datetimes assumed UTC.
#     """
#     try:
#         if not dt_str:
#             raise ValueError("Datetime string required")

#         s = dt_str.strip().replace("Z", "+00:00")
#         parsed = datetime.fromisoformat(s)

#         if parsed.tzinfo is None:
#             parsed = parsed.replace(tzinfo=pytz.UTC)
#         else:
#             parsed = parsed.astimezone(pytz.UTC)

#         return {
#             "success": True,
#             "parsed_utc_iso": parsed.isoformat(),
#             "parsed_utc_readable": parsed.strftime("%Y-%m-%d %H:%M:%S UTC"),
#             "unix_timestamp": int(parsed.timestamp())
#         }


#     except Exception as e:
#         logger.error(f"validate_utc_time error: {e}")
#         return {"success": False, "error": str(e)}
@function_tool
def validate_email(email: str) -> Dict:
    """
    Validate email using RFC 5322 standards and practical rules.
    Detects common typos in popular email domains.

    Args:
        email: Email address to validate

    Returns:
        Dictionary with validation result and suggestions
    """
    logger.info(f"**************Validating email: {email}****************")
    try:
        email = email.strip()

        # Check for exactly one @ symbol
        if email.count("@") != 1:
            return {
                "is_valid": False,
                "error": "Email must have exactly one @ symbol",
                "suggestion": None,
            }

        # Check for spaces
        if " " in email:
            return {
                "is_valid": False,
                "error": "Email cannot contain spaces",
                "suggestion": None,
            }

        # Split into username and domain
        username, domain = email.split("@")

        # Validate username
        if not username:
            return {
                "is_valid": False,
                "error": "Email must have text before @",
                "suggestion": None,
            }

        if username.startswith(".") or username.endswith("."):
            return {
                "is_valid": False,
                "error": "Username cannot start or end with a dot",
                "suggestion": None,
            }

        if ".." in username:
            return {
                "is_valid": False,
                "error": "Username cannot contain consecutive dots",
                "suggestion": None,
            }

        # Validate domain
        if not domain:
            return {
                "is_valid": False,
                "error": "Email must have text after @",
                "suggestion": None,
            }

        if "." not in domain:
            return {
                "is_valid": False,
                "error": "Domain must have at least one dot",
                "suggestion": None,
            }

        if domain.startswith(".") or domain.endswith("."):
            return {
                "is_valid": False,
                "error": "Domain cannot start or end with a dot",
                "suggestion": None,
            }

        if ".." in domain:
            return {
                "is_valid": False,
                "error": "Domain cannot contain consecutive dots",
                "suggestion": None,
            }

        # Check TLD (top-level domain)
        domain_parts = domain.split(".")
        tld = domain_parts[-1]

        if len(tld) < 2:
            return {
                "is_valid": False,
                "error": "Top-level domain must be at least 2 characters",
                "suggestion": None,
            }

        # Check for invalid characters
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.@_-+'"
        )
        # Allow international characters
        email_chars = set(email)
        invalid_chars = email_chars - allowed_chars

        # Filter out international characters (anything above ASCII 127)
        invalid_chars = {c for c in invalid_chars if ord(c) < 128}

        if invalid_chars:
            return {
                "is_valid": False,
                "error": f"Email contains invalid characters: {', '.join(invalid_chars)}",
                "suggestion": None,
            }

        # Common typo detection
        typo_map = {
            "gamil.com": "gmail.com",
            "gmial.com": "gmail.com",
            "gmai.com": "gmail.com",
            "gmail.co": "gmail.com",
            "yahho.com": "yahoo.com",
            "yahooo.com": "yahoo.com",
            "yaho.com": "yahoo.com",
            "yahoo.co": "yahoo.com",
            "hotmial.com": "hotmail.com",
            "hotmil.com": "hotmail.com",
            "hotmail.co": "hotmail.com",
            "outlok.com": "outlook.com",
            "outloo.com": "outlook.com",
            "outlook.co": "outlook.com",
        }

        # Check if domain matches any known typo
        domain_lower = domain.lower()
        if domain_lower in typo_map:
            corrected_email = f"{username}@{typo_map[domain_lower]}"
            return {
                "is_valid": False,
                "error": "Possible typo detected in domain",
                "suggestion": corrected_email,
                "typo_detected": True,
            }

        # Email is valid
        return {
            "is_valid": True,
            "email": email,
            "username": username,
            "domain": domain,
        }

    except Exception as e:
        logger.error(f"Error validating email: {e}")
        return {
            "is_valid": False,
            "error": f"Validation error: {str(e)}",
            "suggestion": None,
        }


@function_tool
def convert_time_to_utc(
    ctx: RunContextWrapper[BotState], time_str: str, date_str: str, timezone: str
) -> Dict[str, Any]:
    """
    Convert a local date and time to UTC ISO format and update state.
    """
    logger.info(
        f"**************************Converting time to UTC: date={date_str}, time={time_str}, timezone={timezone}   ***********************"
    )
    try:
        tz = pytz.timezone(timezone)
        dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        localized_dt = tz.localize(dt)
        utc_dt = localized_dt.astimezone(pytz.UTC)

        result = {
            "success": True,
            "utc_time_iso": utc_dt.isoformat(),
            "utc_time_readable": utc_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "local_time": localized_dt.strftime("%Y-%m-%d %H:%M:%S %Z"),
        }

        if ctx:
            if not ctx.context.user_context.collected_fields:
                ctx.context.user_context.collected_fields = {}
            ctx.context.user_context.collected_fields["date"] = date_str
            ctx.context.user_context.collected_fields["time"] = utc_dt.isoformat()
            ctx.context.user_context.timezone = timezone

        return result
    except Exception as e:
        logger.error(f"convert_time_to_utc error: {e}")
        return {"success": False, "error": str(e)}


@function_tool
def check_calendly_availability(
    date_time_utc_iso: str, tenant_id: str, user_timezone: str
) -> Dict:
    """
    Check if a specific time slot is available in Calendly

    Args:
        date_time_utc_iso: Time in UTC ISO format
        tenant_id: Tenant identifier
        user_timezone: User's timezone for converting slot times

    Returns:
        Dictionary with availability status and alternative slots in local time
    """

    logger.info(
        f"**************Checking Calendly availability for time: {date_time_utc_iso}, tenant_id: {tenant_id}, user_timezone: {user_timezone}****************"
    )
    try:
        # Parse the requested time
        requested_dt = datetime.fromisoformat(date_time_utc_iso.replace("Z", "+00:00"))

        # Call the existing calendly function
        result = calendly_available_slots_api(tenant_id, requested_dt)
        logger.info(f"Calendly availability result: {result}")
        if not result.get("available"):
            return {
                "success": True,
                "is_available": False,
                "requested_time_local": requested_dt.astimezone(
                    pytz.timezone(user_timezone)
                ).strftime("%Y-%m-%d %I:%M %p"),
                "alternative_slots": [],
                "error": result.get("error"),
            }

        # Convert slots to local timezone
        tz = pytz.timezone(user_timezone)
        available_slots = result.get("slots", [])

        # Convert each slot's time to local timezone
        local_slots = []
        for slot in available_slots:
            slot_utc = datetime.fromisoformat(
                slot["start_time_utc"].replace("Z", "+00:00")
            )
            slot_local = slot_utc.astimezone(tz)
            local_slots.append(
                {
                    "start_time_utc": slot["start_time_utc"],
                    "start_time_local": slot_local.strftime("%Y-%m-%d %I:%M %p"),
                    "date": slot_local.strftime("%A, %B %d"),
                    "time": slot_local.strftime("%I:%M %p"),
                    "event_type_name": slot.get("event_type_name"),
                }
            )
        logger.info(f"Local slots: {local_slots}")

        # Normalize requested time for comparison (handle both Z and +00:00 formats)
        requested_utc_normalized = requested_dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Check if requested time matches any available slot (normalize both for comparison)
        is_exact_match = False
        for slot in available_slots:
            slot_utc_str = slot.get("start_time_utc", "")
            # Normalize slot time for comparison
            slot_utc_normalized = (
                slot_utc_str.replace("Z", "").replace("+00:00", "").split(".")[0]
            )

            logger.info(
                f"Comparing: requested={requested_utc_normalized} vs slot={slot_utc_normalized}"
            )

            if requested_utc_normalized == slot_utc_normalized:
                is_exact_match = True
                logger.info(f"MATCH FOUND: {slot_utc_str}")
                break

        max_alternatives = min(7, len(local_slots))

        return {
            "success": True,
            "is_available": is_exact_match,
            "requested_time_local": requested_dt.astimezone(tz).strftime(
                "%Y-%m-%d %I:%M %p"
            ),
            "alternative_slots": local_slots[:max_alternatives],
            "total_alternatives": len(local_slots),
        }
    except Exception as e:
        logger.error(f"Error checking Calendly availability: {e}")
        return {
            "success": False,
            "error": str(e),
            "is_available": False,
            "alternative_slots": [],
        }


# Registere tool for dummy calendly api
@function_tool
def dummy_calendly_api(unused: Optional[str] = None) -> Dict[str, Any]:
    """
    Dummy Calendly API tool for testing.

    """

    logger.info("**************Dummy Calendly API called****************")
