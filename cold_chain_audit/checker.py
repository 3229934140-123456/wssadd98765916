from typing import List, Dict
from datetime import datetime, timedelta
from .models import (
    Waybill, TemperatureRecord, AuditResult,
    OverTempSegment
)


def _find_continuous_overtemp(
    records: List[TemperatureRecord],
    temp_max: float,
    min_duration_minutes: int,
    start_time: datetime,
    end_time: datetime
) -> List[OverTempSegment]:
    segments: List[OverTempSegment] = []
    in_transit = [r for r in records if start_time <= r.record_time <= end_time]
    if not in_transit:
        return segments

    current_seg_start = None
    current_max_temp = None

    for i, rec in enumerate(in_transit):
        if rec.temperature > temp_max:
            if current_seg_start is None:
                current_seg_start = rec.record_time
                current_max_temp = rec.temperature
            else:
                if rec.temperature > current_max_temp:
                    current_max_temp = rec.temperature
        else:
            if current_seg_start is not None:
                prev_rec = in_transit[i - 1] if i > 0 else rec
                duration = (prev_rec.record_time - current_seg_start).total_seconds() / 60.0
                if duration >= min_duration_minutes:
                    segments.append(OverTempSegment(
                        start_time=current_seg_start,
                        end_time=prev_rec.record_time,
                        max_temp=current_max_temp,
                        duration_minutes=round(duration, 1)
                    ))
                current_seg_start = None
                current_max_temp = None

    if current_seg_start is not None:
        last_rec = in_transit[-1]
        duration = (last_rec.record_time - current_seg_start).total_seconds() / 60.0
        if duration >= min_duration_minutes:
            segments.append(OverTempSegment(
                start_time=current_seg_start,
                end_time=last_rec.record_time,
                max_temp=current_max_temp,
                duration_minutes=round(duration, 1)
            ))

    return segments


def _get_temp_at_or_before(records: List[TemperatureRecord], target: datetime) -> float:
    candidates = [r for r in records if r.record_time <= target]
    if not candidates:
        candidates = records
    if not candidates:
        return 0.0
    candidates.sort(key=lambda r: r.record_time)
    return candidates[-1].temperature


def audit_waybill(
    waybill: Waybill,
    temp_records: List[TemperatureRecord]
) -> AuditResult:
    sorted_records = sorted(temp_records, key=lambda r: r.record_time)
    in_transit = [r for r in sorted_records if waybill.load_time <= r.record_time <= waybill.unload_time]

    if in_transit:
        temps = [r.temperature for r in in_transit]
        actual_min = min(temps)
        actual_max = max(temps)
    else:
        actual_min = 0.0
        actual_max = 0.0

    pre_cool_ok = True
    pre_cool_temp_at_load = _get_temp_at_or_before(sorted_records, waybill.load_time)
    if waybill.pre_cool_required and sorted_records and pre_cool_temp_at_load > waybill.pre_cool_temp:
        pre_cool_ok = False

    if not sorted_records:
        pre_cool_temp_at_load = 0.0

    overtemp_segments = _find_continuous_overtemp(
        sorted_records,
        waybill.target_temp_max,
        waybill.continuous_overtemp_minutes,
        waybill.load_time,
        waybill.unload_time
    )
    has_continuous_overtemp = len(overtemp_segments) > 0
    overtemp_total_minutes = round(sum(s.duration_minutes for s in overtemp_segments), 1)
    overtemp_max_temp = max((s.max_temp for s in overtemp_segments), default=0.0)

    post_unload = [r for r in sorted_records if r.record_time > waybill.unload_time]
    post_unload_minutes = 0.0
    post_unload_max_temp = 0.0
    has_post_unload_data = False
    if post_unload:
        first_after = post_unload[0].record_time
        gap = (first_after - waybill.unload_time).total_seconds() / 60.0
        if gap < 60:
            last_after = post_unload[-1].record_time
            post_unload_minutes = (last_after - waybill.unload_time).total_seconds() / 60.0
            post_unload_temps = [r.temperature for r in post_unload]
            post_unload_max_temp = max(post_unload_temps)
            if post_unload_minutes > 30:
                has_post_unload_data = True

    actual_duration = (waybill.unload_time - waybill.load_time).total_seconds() / 60.0

    is_abnormal = False
    suggestions: List[str] = []

    if not sorted_records:
        is_abnormal = True
        suggestions.append("缺少运输温度数据，无法判断温度合规性，需核查记录仪导出文件")
    else:
        if not pre_cool_ok:
            is_abnormal = True
            suggestions.append(
                f"装车前未预冷：装车时温度{pre_cool_temp_at_load:.1f}℃，"
                f"高于要求{waybill.pre_cool_temp:.1f}℃，需加强预冷管理"
            )

        if has_continuous_overtemp:
            is_abnormal = True
            suggestions.append(
                f"途中连续超温{len(overtemp_segments)}段，"
                f"累计{overtemp_total_minutes:.0f}分钟，最高超温{overtemp_max_temp:.1f}℃，"
                f"需核查制冷设备及装卸操作"
            )

        if has_post_unload_data:
            is_abnormal = True
            suggestions.append(
                f"卸货后仍有{post_unload_minutes:.0f}分钟温度记录"
                f"(最高{post_unload_max_temp:.1f}℃)，"
                f"可能存在运单时长计算错误或记录仪未及时关闭"
            )

        if not in_transit:
            is_abnormal = True
            suggestions.append("运输途中无温度记录数据，无法判断温度合规性")

    return AuditResult(
        waybill_no=waybill.waybill_no,
        plate_number=waybill.plate_number,
        customer=waybill.customer,
        meat_type=waybill.meat_type,
        target_temp_min=waybill.target_temp_min,
        target_temp_max=waybill.target_temp_max,
        actual_temp_min=round(actual_min, 2),
        actual_temp_max=round(actual_max, 2),
        load_time=waybill.load_time,
        unload_time=waybill.unload_time,
        actual_duration_minutes=round(actual_duration, 1),
        pre_cool_ok=pre_cool_ok,
        pre_cool_temp_at_load=round(pre_cool_temp_at_load, 2),
        has_continuous_overtemp=has_continuous_overtemp,
        has_post_unload_data=has_post_unload_data,
        post_unload_minutes=round(post_unload_minutes, 1),
        is_abnormal=is_abnormal,
        pre_cool_required=waybill.pre_cool_required,
        pre_cool_temp=waybill.pre_cool_temp,
        continuous_overtemp_minutes=waybill.continuous_overtemp_minutes,
        has_standard=waybill.has_standard,
        overtemp_segments=overtemp_segments,
        suggestions=suggestions,
        temp_records_count=len(in_transit),
        matched_total_count=len(sorted_records),
        post_unload_max_temp=round(post_unload_max_temp, 2),
        overtemp_total_minutes=overtemp_total_minutes,
        overtemp_max_temp=round(overtemp_max_temp, 2)
    )


def audit_all(
    waybills: List[Waybill],
    matched_temps: Dict[str, List[TemperatureRecord]]
) -> List[AuditResult]:
    results = []
    for wb in waybills:
        temps = matched_temps.get(wb.waybill_no, [])
        result = audit_waybill(wb, temps)
        results.append(result)
    return results
