from typing import List, Dict
from collections import defaultdict
from datetime import timedelta
from .models import TemperatureRecord, Waybill


def match_waybills_with_temps(
    waybills: List[Waybill],
    temp_records: List[TemperatureRecord],
    pre_cool_window_minutes: int = 30,
    post_unload_window_minutes: int = 120
) -> Dict[str, List[TemperatureRecord]]:
    wb_no_temps: Dict[str, List[TemperatureRecord]] = defaultdict(list)
    plate_temps_no_wb: Dict[str, List[TemperatureRecord]] = defaultdict(list)

    for rec in temp_records:
        if rec.waybill_no:
            wb_no_temps[rec.waybill_no].append(rec)
        else:
            plate_temps_no_wb[rec.plate_number].append(rec)

    for key in wb_no_temps:
        wb_no_temps[key].sort(key=lambda r: r.record_time)
    for key in plate_temps_no_wb:
        plate_temps_no_wb[key].sort(key=lambda r: r.record_time)

    wb_by_plate: Dict[str, List[Waybill]] = defaultdict(list)
    for wb in waybills:
        wb_by_plate[wb.plate_number].append(wb)
    for plate in wb_by_plate:
        wb_by_plate[plate].sort(key=lambda w: w.load_time)

    consumed_indices: Dict[str, set] = defaultdict(set)
    result: Dict[str, List[TemperatureRecord]] = {}

    for wb in waybills:
        matched: List[TemperatureRecord] = []

        if wb.waybill_no in wb_no_temps:
            matched.extend(wb_no_temps[wb.waybill_no])

        candidates = plate_temps_no_wb.get(wb.plate_number, [])
        plate_wbs = wb_by_plate.get(wb.plate_number, [])

        wb_idx = None
        for i, pw in enumerate(plate_wbs):
            if pw.waybill_no == wb.waybill_no:
                wb_idx = i
                break

        prev_unload = None
        next_load = None
        if wb_idx is not None:
            if wb_idx > 0:
                prev_unload = plate_wbs[wb_idx - 1].unload_time
            if wb_idx < len(plate_wbs) - 1:
                next_load = plate_wbs[wb_idx + 1].load_time

        start_bound = wb.load_time - timedelta(minutes=pre_cool_window_minutes)
        end_bound = wb.unload_time + timedelta(minutes=post_unload_window_minutes)

        if prev_unload is not None:
            gap_start = prev_unload + timedelta(minutes=5)
            if gap_start > start_bound:
                start_bound = gap_start

        if next_load is not None:
            gap_end = next_load - timedelta(minutes=5)
            if gap_end < end_bound:
                end_bound = gap_end

        for idx, r in enumerate(candidates):
            if idx in consumed_indices.get(wb.plate_number, set()):
                continue
            if start_bound <= r.record_time <= end_bound:
                matched.append(r)
                consumed_indices[wb.plate_number].add(idx)

        matched.sort(key=lambda r: r.record_time)
        result[wb.waybill_no] = matched

    return result
