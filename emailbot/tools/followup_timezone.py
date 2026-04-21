"""
This module contains tool for the Agents application.
"""

from agents import function_tool, RunContextWrapper
import pytz
from emailbot.core.state import BotState
from opik import track
from emailbot.config.settings import logger
import json
from datetime import datetime, timedelta, time
from typing import Dict, Any
import re


@function_tool
@track
def get_timezone(ctx: RunContextWrapper[BotState], region_code: str) -> dict:
    """
    Get all available timezones for a given region code (ISO 3166-1 alpha-2).
    """
    try:
        # Handle cases where LLM passes a JSON string (as seen in logs)
        if isinstance(region_code, str) and "{" in region_code:
            try:
                import json

                region_code = json.loads(region_code).get("region_code", region_code)
            except:
                pass

        # Normalize and handle stringified nulls/placeholders from the LLM
        if not region_code or str(region_code).upper() in [
            "NONE",
            "NULL",
            "UNDEFINED",
            "NOT PROVIDED",
            "UNKNOWN",
        ]:
            return {
                "region_code": None,
                "ismultiple_timezone": False,
                "timezone": None,
                "error": "No valid region_code provided. Ask the user for their location.",
            }

        region_code = str(region_code).strip().upper()
        timezones = pytz.country_timezones.get(region_code, [])

        if not timezones:
            return {
                "region_code": region_code,
                "ismultiple_timezone": False,
                "timezone": None,
                "error": f"Invalid country code '{region_code}'. No timezones found.",
            }

        # If Multiple Timezones Present
        if len(timezones) > 1:
            ismultiple_timezone = True
            timezone = timezones
        else:
            # If Single Timezone Present
            ismultiple_timezone = False
            timezone = timezones[0] if timezones else None

        # Update state directly (only if we have a valid single timezone)
        if ctx:
            ctx.context.user_context.region_code = region_code
            ctx.context.user_context.ismultiple_timezone = ismultiple_timezone
            if not ismultiple_timezone:
                ctx.context.user_context.timezone = timezone

    except Exception as e:
        logger.error(f"Error In Get Timezone Utils: {str(e)}")
        ismultiple_timezone = False
        timezone = None
        region_code = None

    return {
        "region_code": region_code,
        "ismultiple_timezone": ismultiple_timezone,
        "timezone": timezone,
    }


@function_tool
@track
def process_followup_datetime(
    ctx: RunContextWrapper[BotState], datetime_expression: str, timezone: str
) -> Dict[str, Any]:
    """
    Unified tool for processing follow-up datetime expressions.

    Combines parsing, validation, and UTC conversion in a single call.
    Handles relative expressions like "in 30 minutes", "tomorrow at 3 PM", "next Monday", etc.

    Args:
        datetime_expression: Natural language datetime (e.g., "in 30 minutes", "tomorrow at 3 PM")
        timezone: User's timezone (IANA format like "Asia/Kolkata")

    Returns:
        Dictionary with:
        - success: true/false
        - date: "YYYY-MM-DD"
        - time: "HH:MM"
        - utc_time_iso: "YYYY-MM-DDTHH:MM:SS+00:00"
        - local_time_readable: Human-readable local time
        - day_of_week: "Monday", "Tuesday", etc.
        - next_action: "confirm" | "ask_correction"
        - message: Info/error message
        - is_past: true if time is in the past
        - is_too_far: true if >90 days in future
    """
    logger.info(
        f"[process_followup_datetime] Processing: '{datetime_expression}' in timezone: {timezone}"
    )

    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        text = datetime_expression.lower().strip()
        text_no_comma = text.replace(",", " ")

        # --- Pre-normalize: convert word numbers to digits ---
        word_to_num = {
            "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
            "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
            "eleven": "11", "twelve": "12", "fifteen": "15", "twenty": "20",
            "thirty": "30", "forty": "40", "forty-five": "45", "forty five": "45",
            "sixty": "60", "ninety": "90",
            # Hindi word numbers
            "ek": "1", "do": "2", "teen": "3", "char": "4", "paanch": "5",
            "chhe": "6", "saat": "7", "aath": "8", "nau": "9", "das": "10",
            "pandrah": "15", "bees": "20", "tees": "30",
        }
        for word, digit in word_to_num.items():
            text = re.sub(r'\b' + re.escape(word) + r'\b', digit, text)
            text_no_comma = re.sub(r'\b' + re.escape(word) + r'\b', digit, text_no_comma)

        # --- Step 1: Parse relative time expression ---
        hour = minute = None
        has_time = False
        target = None

        # Extract explicit time (AM/PM or 24h format) - check multiple patterns
        match_ampm = re.search(r"(\d{1,2})[:.]?(\d{2})?\s*(am|pm)", text, re.IGNORECASE)
        match_24 = re.search(r"\b(\d{1,2}):(\d{2})\b", text)
        match_bare_hour = re.search(r'\b(\d{1,2})\s*(?:o\'?clock|oclock|hrs?|h)?\b(?![:\.\d])', text)

        # Handle "noon", "midnight", or other time-of-day references
        time_of_day_map = {
            "noon": (12, 0),
            "midnight": (0, 0),
            "morning": (10, 0),
            "afternoon": (14, 0),
            "evening": (18, 0),
            "night": (20, 0),
            "lunch": (14, 0),
        }

        for time_word, (h, m) in time_of_day_map.items():
            if time_word in text:
                hour = h
                minute = m
                has_time = True
                break

        # Override with explicit time if found (priority: AM/PM > 24h format > bare hour)
        if match_ampm and not has_time:
            hour = int(match_ampm.group(1))
            minute = int(match_ampm.group(2)) if match_ampm.group(2) else 0
            am_pm = match_ampm.group(3).lower()
            if am_pm == "pm" and hour < 12:
                hour += 12
            elif am_pm == "am" and hour == 12:
                hour = 0
            has_time = True
        elif match_24 and not has_time:
            h = int(match_24.group(1))
            if 0 <= h <= 23:
                hour = h
                minute = int(match_24.group(2))
                has_time = True
        elif match_bare_hour and not has_time:
            # Handle bare hour like "7", "2", "14"
            bare_h = int(match_bare_hour.group(1))
            if 0 <= bare_h <= 23:
                current_hour = now.hour
                # If bare hour is greater than current hour, assume it's later today
                # Otherwise assume it refers to the same day (will be caught by is_past check)
                hour = bare_h
                minute = 0
                has_time = True

        # --- Unit abbreviation map (reused across multiple patterns) ---
        unit_map = {
            "min": "minutes", "mins": "minutes", "minute": "minutes", "minutes": "minutes",
            "m": "minutes",
            "hr": "hours", "hrs": "hours", "hour": "hours", "hours": "hours",
            "h": "hours",
            "day": "days", "days": "days", "d": "days",
            "week": "weeks", "weeks": "weeks", "wk": "weeks", "wks": "weeks",
            "sec": "seconds", "secs": "seconds", "second": "seconds", "seconds": "seconds",
            # Hindi units
            "ghante": "hours", "ghanta": "hours", "ghnte": "hours",
            "minute": "minutes", "minat": "minutes",
            "din": "days", "hafte": "weeks", "hafta": "weeks",
        }

        # Unit pattern for regex (sorted by length desc to match longer first)
        _unit_words = sorted(unit_map.keys(), key=len, reverse=True)
        _unit_pattern = "|".join(re.escape(u) for u in _unit_words)

        # --- Pattern 1: "in X units" / "after X units" ---
        rel_match = re.search(
            rf"(?:in|after|baad)\s+(\d+)\s*({_unit_pattern})",
            text
        )

        # --- Pattern 2: "X units" without prefix (e.g., "5 mins", "10 min") ---
        if not rel_match:
            rel_match = re.search(
                rf"^(\d+)\s*({_unit_pattern})\b",
                text
            )

        # --- Pattern 3: "X units later/from now/se" ---
        if not rel_match:
            rel_match = re.search(
                rf"(\d+)\s*({_unit_pattern})\s+(?:later|from now|from\s+now|baad|mein|me|mai|se)",
                text
            )

        if rel_match:
            amount = int(rel_match.group(1))
            unit_raw = rel_match.group(2)
            unit = unit_map.get(unit_raw, "minutes")
            delta = timedelta(**{unit: amount})
            target = now + delta

        # --- Pattern 4: "half an hour", "half hour", "aadha ghanta" ---
        if not target and re.search(r"(?:half\s+(?:an?\s+)?hour|aadha\s+ghant[ae])", text):
            target = now + timedelta(minutes=30)

        # --- Pattern 5: "an hour", "one hour", "ek ghanta" ---
        if not target and re.search(r"(?:an?\s+hour|ek\s+ghant[ae])", text):
            target = now + timedelta(hours=1)

        # --- Pattern 6: "a minute", "a min", "ek minute" ---
        if not target and re.search(r"(?:an?\s+min(?:ute)?|ek\s+min(?:ute|at)?)", text):
            target = now + timedelta(minutes=1)

        # --- Pattern 7: "couple of hours/minutes", "few minutes" ---
        if not target:
            couple_match = re.search(
                rf"(?:a\s+)?(?:couple|couple\s+of|few)\s+({_unit_pattern})",
                text
            )
            if couple_match:
                unit_raw = couple_match.group(1)
                unit = unit_map.get(unit_raw, "minutes")
                amount = 2 if "couple" in text else 3  # couple=2, few=3
                delta = timedelta(**{unit: amount})
                target = now + delta

        # --- Pattern 8: "quarter hour", "quarter of an hour" ---
        if not target and re.search(r"quarter\s+(?:of\s+)?(?:an?\s+)?hour", text):
            target = now + timedelta(minutes=15)

        # Handle "tomorrow" / "kal"
        if not target and ("tomorrow" in text or "kal" in text):
            target = now + timedelta(days=1)
            if has_time:
                target = target.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            else:
                target = target.replace(
                    hour=14, minute=0, second=0, microsecond=0
                )  # Default 2 PM

        # Handle "today" / "aaj" AND bare time without day indicator
        if not target and ("today" in text or "aaj" in text or (has_time and not any(day_word in text for day_word in ["tomorrow", "kal", "next", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "week", "hafte"]))):
            target = now
            if has_time:
                target = target.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            else:
                # If no time specified for "today", but might be in context, default to 1 hour from now
                target = now + timedelta(hours=1)

        # Handle "next week" / "agle hafte"
        if not target and ("next week" in text or "agle hafte" in text):
            target = now + timedelta(days=7)
            if has_time:
                target = target.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )
            else:
                target = target.replace(hour=14, minute=0, second=0, microsecond=0)

        # Handle explicit dates (e.g., "9th dec", "December 9", "12/9/2025", "Feb 10 at 3pm")
        if not target:
            date_patterns = [
                # "9th dec 2026", "9 december 2025", "8th December, 2026"
                r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*(\d{4})?",
                # "dec 9", "december 9th 2025"
                r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?\s*(\d{4})?",
                # "12/9/2025", "9-12-2025"
                r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{4})",
                # "2025-12-09"
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
                match = re.search(pattern, text_no_comma)
                if match:
                    groups = match.groups()
                    year = None
                    month = None
                    day = None

                    # Parse different date formats
                    if len(groups) == 3 and groups[1] in month_map:
                        day = int(groups[0])
                        month = month_map[groups[1]]
                        year = int(groups[2]) if groups[2] else None
                    elif len(groups) == 3 and groups[0] in month_map:
                        month = month_map[groups[0]]
                        day = int(groups[1])
                        year = int(groups[2]) if groups[2] else None
                    elif (
                        len(groups) == 3 and groups[0].isdigit() and len(groups[0]) <= 2
                    ):
                        day = int(groups[0])
                        month = int(groups[1])
                        year = int(groups[2])
                    elif len(groups) == 3 and len(groups[0]) == 4:
                        year = int(groups[0])
                        month = int(groups[1])
                        day = int(groups[2])

                    # Handle missing year
                    if year is None:
                        year = now.year
                        if month < now.month or (month == now.month and day < now.day):
                            year = now.year + 1

                    if day and month and year:
                        try:
                            target = now.replace(
                                year=year,
                                month=month,
                                day=day,
                                hour=14,
                                minute=0,
                                second=0,
                                microsecond=0,
                            )
                            if has_time:
                                target = target.replace(hour=hour, minute=minute)
                            break
                        except ValueError:
                            continue

        # Handle weekday references (this/next Monday, Friday, etc.)
        if not target:
            days_of_week = [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
            for i, day_name in enumerate(days_of_week):
                if day_name in text:
                    current_weekday = now.weekday()
                    target_weekday = i
                    days_ahead = (target_weekday - current_weekday) % 7

                    # If "next" is explicitly mentioned OR it's the same weekday, go to next week
                    if "next" in text or days_ahead == 0:
                        days_ahead = 7 if days_ahead == 0 else days_ahead

                    target = now + timedelta(days=days_ahead)
                    if has_time:
                        target = target.replace(
                            hour=hour, minute=minute, second=0, microsecond=0
                        )
                    else:
                        target = target.replace(
                            hour=14, minute=0, second=0, microsecond=0
                        )  # Default 2 PM
                    break

        # If we couldn't parse the expression
        if target is None:
            return {
                "success": False,
                "next_action": "ask_correction",
                "message": f"I couldn't understand '{datetime_expression}'. Please try: 'in 30 minutes', 'tomorrow at 3 PM', 'next Monday', etc.",
                "error": "Could not parse datetime expression",
            }

        # --- Step 2: Validate the parsed datetime ---
        is_past = target < now
        is_too_far = target > (now + timedelta(days=90))

        if is_past:
            # Format a helpful message showing what time was requested and why it's invalid
            requested_time = target.strftime("%I:%M %p")
            current_time = now.strftime("%I:%M %p")
            return {
                "success": False,
                "next_action": "ask_correction",
                "date": target.strftime("%Y-%m-%d"),
                "time": target.strftime("%H:%M"),
                "is_past": True,
                "message": f"{requested_time} has already passed (current time: {current_time}). Please choose a future time.",
                "current_time_for_ref": now.strftime("%Y-%m-%d %H:%M"),
            }

        if is_too_far:
            return {
                "success": False,
                "next_action": "ask_correction",
                "message": f"That's more than 90 days away. Please choose a time within the next 3 months.",
                "is_too_far": True,
            }

        # --- Step 3: Convert to UTC ---
        utc_target = target.astimezone(pytz.UTC)

        # Format for output
        date_str = target.strftime("%Y-%m-%d")
        time_str = target.strftime("%H:%M")

        # --- Step 4: Update state ---
        if ctx:
            if not ctx.context.user_context.collected_fields:
                ctx.context.user_context.collected_fields = {}
            # Only set followup_time — do NOT overwrite date/time (those are booking fields)
            ctx.context.user_context.collected_fields["followup_time"] = (
                utc_target.isoformat()
            )
            ctx.context.user_context.timezone = timezone
            logger.info(
                f"[process_followup_datetime] State updated: date={date_str}, time={time_str}, followup_time={utc_target.isoformat()}"
            )

        # --- Step 5: Return success response ---
        return {
            "success": True,
            "date": date_str,
            "time": time_str,
            "utc_time_iso": utc_target.isoformat(),
            "local_time_readable": target.strftime("%A, %B %d at %I:%M %p"),
            "day_of_week": target.strftime("%A"),
            "next_action": "confirm",
            "message": f"Follow-up scheduled for {target.strftime('%A, %B %d at %I:%M %p')} ({timezone})",
            "is_past": False,
            "is_too_far": False,
        }

    except Exception as e:
        logger.error(f"[process_followup_datetime] Error: {e}")
        return {
            "success": False,
            "next_action": "ask_correction",
            "message": f"Error processing datetime: {str(e)}",
            "error": str(e),
        }