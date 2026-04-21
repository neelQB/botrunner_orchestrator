import requests
import datetime
import os


from emailbot.config.settings import logger
from datetime import timedelta


_EVENT_TYPE_URI = "https://api.calendly.com/event_types/1b761a53-2f5c-4958-a782-027e08cb0fe9"
_LOCAL_SLOT_TIMES = [(11, 0), (13, 0), (16, 0), (17, 0), (19, 0)]   # IST slot times
_VALID_WEEKDAYS = {0, 1, 2, 3, 4, 5}                                  # Mon-Sat; Sunday excluded
_IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _generate_mock_slots(num_slots: int = 10) -> list:
    """
    Generate `num_slots` upcoming mock available slots starting from now.
    Slots are created Mon-Sat at 11:00, 13:00, 16:00, 17:00, 19:00 IST.
    """
    slots = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    current_date = now_utc.date()

    while len(slots) < num_slots:
        if current_date.weekday() in _VALID_WEEKDAYS:
            for hour, minute in _LOCAL_SLOT_TIMES:
                if len(slots) >= num_slots:
                    break

                local_dt = datetime.datetime(
                    current_date.year, current_date.month, current_date.day,
                    hour, minute, tzinfo=_IST
                )
                utc_dt = local_dt.astimezone(datetime.timezone.utc)

                if utc_dt <= now_utc:
                    continue

                slots.append({
                    "start_time_utc": utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "start_time_local": f"{current_date} {hour:02d}:{minute:02d}",
                    "status": "available",
                    "event_type_name": "30 Minute Meeting",
                    "event_type_uri": _EVENT_TYPE_URI,
                    "event_location_kind": "google_conference",
                })

        current_date += datetime.timedelta(days=1)

    return slots


def calendly_available_slots_api(tenant_id, slot_datetime):
    # ------------------UNCOMMENT CODE BELOW FOR ACTUAL API USE-------------------------#
    # try:
    #     minutes = slot_datetime.minute
    #     if minutes > 0 and minutes != 30:
    #         minutes_to_add = 30 - (minutes % 30)
    #         rounded_datetime = slot_datetime.replace(second=0, microsecond=0) + timedelta(minutes=minutes_to_add)
    #     else:
    #         rounded_datetime = slot_datetime.replace(second=0, microsecond=0)

    #     print("slot_datetime", slot_datetime)

    #     search_start_utc = rounded_datetime
    #     print("search_start_utc", search_start_utc)
    #     search_end_utc = search_start_utc + timedelta(days=7)
    #     search_start_iso = search_start_utc.isoformat(timespec='seconds').replace("+00:00", "Z")
    #     search_end_iso = search_end_utc.isoformat(timespec='seconds').replace("+00:00", "Z")

    #     key = os.getenv("CALENDY_KEY")

    #     headers = {
    #         "Authorization": f"Bearer {key}",
    #         "Content-Type": "application/json"
    #     }

    #     def make_request(url, params=None):
    #         resp = requests.get(url, headers=headers, params=params or {}, timeout=10)
    #         if resp.status_code == 401:
    #             logger.error(f"Calendly 401 - refreshing token for integration")
    #         else:
    #             logger.error("Failed to refresh Calendly token")
    #         return resp

    #     event_types_resp = make_request(
    #         "https://api.calendly.com/event_types",
    #         params={"organization": "https://api.calendly.com/organizations/631cc414-d145-4901-bb06-5cf251ce60a2", "active": True}
    #     )

    #     if not event_types_resp.ok:
    #         logger.error(f"Failed to fetch event types: {event_types_resp.status_code} {event_types_resp.text}")
    #         return {"available": False, "slots": [], "error": "Failed to fetch event types"}

    #     event_types = event_types_resp.json().get("collection", [])
    #     if not event_types:
    #         return {"available": False, "slots": [], "error": "No active event types"}

    #     available_slots = []

    #     for event_type in event_types:
    #         if len(available_slots) >= 5:
    #             break

    #         event_type_uri = event_type["uri"]

    #         slots_resp = make_request(
    #             "https://api.calendly.com/event_type_available_times",
    #             params={
    #                 "event_type": event_type_uri,
    #                 "start_time": search_start_iso,
    #                 "end_time": search_end_iso
    #             }
    #         )

    #         if not slots_resp.ok:
    #             logger.warning(f"Failed to get slots for {event_type['name']}: {slots_resp.text}")
    #             continue

    #         slots = slots_resp.json().get("collection", [])
    #         for slot in slots:
    #             slot_time_str = slot.get("start_time")

    #             slot_utc = datetime.datetime.fromisoformat(slot_time_str.replace("Z", "+00:00"))
    #             slot_local = slot_utc.astimezone(slot_datetime.tzinfo) if slot_datetime.tzinfo else slot_utc

    #             available_slots.append({
    #                 "start_time_utc": slot_time_str,
    # #                 "start_time_local": slot_local.strftime("%Y-%m-%d %H:%M"),
    #                 "status": slot.get("status"),
    #                 "event_type_name": event_type.get("name"),
    #                 "event_type_uri": event_type_uri,
    #                 "event_location_kind": event_type["locations"][0]["kind"],
    #             })

    #             if len(available_slots) >= 5:
    #                 break
    #     if len(available_slots)==0:
    #         return {
    #             "available": False,
    #             "slots": [],
    #             "error": "No available slots"
    #         }

    #     logger.info(f"\n\n\n available_slots : {available_slots} \n\n\n")

    #     return {
    #         "available": len(available_slots) > 0,
    #         "count": len(available_slots),
    #         "slots": available_slots[:5],
    #         "searched_from": search_start_iso,
    #         "searched_to": search_end_iso,
    #         "timezone": str(slot_datetime.tzinfo) if slot_datetime.tzinfo else "UTC"
    #     }

    # except Exception as e:
    #     logger.exception(f"Unexpected error in calendly_available_slots: {str(e)}")
    #     return {"available": False, "slots": [], "error": str(e)}

    # #------------------MOCKED RESPONSE FOR DEMO PURPOSES-------------------------#
    try:
        minutes = slot_datetime.minute
        if minutes > 0 and minutes != 30:
            minutes_to_add = 30 - (minutes % 30)
            rounded_datetime = slot_datetime.replace(second=0, microsecond=0) + timedelta(
                minutes=minutes_to_add
            )
        else:
            rounded_datetime = slot_datetime.replace(second=0, microsecond=0)

        print("slot_datetime", slot_datetime)

        search_start_utc = rounded_datetime
        print("search_start_utc", search_start_utc)
        search_end_utc = search_start_utc + timedelta(days=7)
        search_start_iso = search_start_utc.isoformat(timespec="seconds").replace(
            "+00:00", "Z"
        )
        search_end_iso = search_end_utc.isoformat(timespec="seconds").replace("+00:00", "Z")
        available_slots = _generate_mock_slots(num_slots=15)


        return {
            "available": len(available_slots) > 0,
            "count": len(available_slots),
            "slots": available_slots,
            "searched_from": search_start_iso,
            "searched_to": search_end_iso,
            "timezone": str(slot_datetime.tzinfo) if slot_datetime.tzinfo else "UTC",
        }
    except Exception as e:
        logger.error(f"Error in mock calendly_available_slots_api: {e}")
        return {
            "available": False,
            "slots": [],
            "error": str(e)
        }
