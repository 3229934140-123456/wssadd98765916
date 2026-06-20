from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class TemperatureRecord:
    plate_number: str
    record_time: datetime
    temperature: float
    waybill_no: str = ""


@dataclass
class Waybill:
    waybill_no: str
    plate_number: str
    customer: str
    meat_type: str
    load_time: datetime
    unload_time: datetime
    target_temp_min: float
    target_temp_max: float
    pre_cool_required: bool = True
    pre_cool_temp: float = 0.0
    continuous_overtemp_minutes: int = 10
    has_standard: bool = True


@dataclass
class CustomerStandard:
    customer: str
    meat_type: str
    temp_min: float
    temp_max: float
    pre_cool_required: bool
    pre_cool_temp: float
    continuous_overtemp_minutes: int


@dataclass
class OverTempSegment:
    start_time: datetime
    end_time: datetime
    max_temp: float
    duration_minutes: float


@dataclass
class AuditResult:
    waybill_no: str
    plate_number: str
    customer: str
    meat_type: str
    target_temp_min: float
    target_temp_max: float
    actual_temp_min: float
    actual_temp_max: float
    load_time: datetime
    unload_time: datetime
    actual_duration_minutes: float
    pre_cool_ok: bool
    pre_cool_temp_at_load: float
    has_continuous_overtemp: bool
    has_post_unload_data: bool
    post_unload_minutes: float
    is_abnormal: bool
    pre_cool_required: bool = True
    pre_cool_temp: float = 0.0
    continuous_overtemp_minutes: int = 10
    has_standard: bool = True
    overtemp_segments: List[OverTempSegment] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    temp_records_count: int = 0
    matched_total_count: int = 0
    summary_file_path: str = ""
    review_status: str = "待复核"
    post_unload_max_temp: float = 0.0
    overtemp_total_minutes: float = 0.0
    overtemp_max_temp: float = 0.0
