import os
import csv
import glob
from typing import List, Dict
from .models import AuditResult


def find_latest_review_csv(output_dir: str) -> str:
    if not os.path.isdir(output_dir):
        return ""
    pattern = os.path.join(output_dir, "复核交接单_*.csv")
    files = glob.glob(pattern)
    if not files:
        return ""
    files.sort(key=os.path.getmtime, reverse=True)
    return files[0]


def load_review_statuses(csv_path: str) -> Dict[str, str]:
    statuses: Dict[str, str] = {}
    if not csv_path or not os.path.isfile(csv_path):
        return statuses
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                wb_no = row.get("运单号", "").strip()
                status = row.get("复核状态", "").strip()
                if wb_no and status in ("待复核", "已确认", "已放行", "正常"):
                    statuses[wb_no] = status
    except Exception:
        pass
    return statuses


def apply_review_statuses(results: List[AuditResult], statuses: Dict[str, str]) -> int:
    updated = 0
    for r in results:
        if r.waybill_no in statuses:
            saved = statuses[r.waybill_no]
            if saved == "正常":
                if not r.is_abnormal:
                    r.review_status = "待复核"
                else:
                    r.review_status = "待复核"
                    updated += 1
            else:
                if r.is_abnormal:
                    r.review_status = saved
                    updated += 1
        else:
            if r.is_abnormal and r.review_status != "待复核":
                r.review_status = "待复核"
    return updated
