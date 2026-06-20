from typing import List, Dict
from collections import defaultdict
from datetime import timedelta
from .models import TemperatureRecord, Waybill


def match_waybills_with_temps(
    waybills: List[Waybill],
    temp_records: List[TemperatureRecord],
    pre_cool_window_minutes: int = 60
) -> Dict[str, List[TemperatureRecord]]:
    plate_temps: Dict[str, List[TemperatureRecord]] = defaultdict(list)
    for rec in temp_records:
        plate_temps[rec.plate_number].append(rec)

    for plate in plate_temps:
        plate_temps[plate].sort(key=lambda r: r.record_time)

    result: Dict[str, List[TemperatureRecord]] = {}

    for wb in waybills:
        wb_key = wb.waybill_no
        plate = wb.plate_number
        candidates = plate_temps.get(plate, [])

        start_bound = wb.load_time - timedelta(minutes=pre_cool_window_minutes)
        end_bound = wb.unload_time + timedelta(minutes=pre_cool_window_minutes)

        matched = [
            r for r in candidates
            if start_bound <= r.record_time <= end_bound
        ]

        result[wb_key] = matched

    return result
