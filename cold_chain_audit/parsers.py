import os
import glob
import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple
from .models import TemperatureRecord, Waybill, CustomerStandard


def _read_any_table(file_path: str) -> pd.DataFrame:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in ('.csv', '.txt'):
        encodings = ['utf-8-sig', 'gbk', 'utf-8']
        for enc in encodings:
            try:
                return pd.read_csv(file_path, encoding=enc)
            except (UnicodeDecodeError, UnicodeError):
                continue
        raise ValueError(f"无法读取文件编码: {file_path}")
    elif ext in ('.xlsx', '.xls'):
        return pd.read_excel(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {file_path}")


def _find_col(df: pd.DataFrame, candidates: List[str]) -> str:
    df_cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in df_cols_lower:
            return df_cols_lower[cand.lower()]
    raise KeyError(f"未找到列，候选: {candidates}, 实际列: {list(df.columns)}")


def parse_temperature_files(folder: str) -> List[TemperatureRecord]:
    records: List[TemperatureRecord] = []
    patterns = ['*.csv', '*.txt', '*.xlsx', '*.xls']
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(folder, pat)))
    files = sorted(set(files))

    for fp in files:
        try:
            df = _read_any_table(fp)
            plate_col = _find_col(df, ['车牌', '车牌号', 'plate', 'plate_number', '车号'])
            time_col = _find_col(df, ['时间', '记录时间', 'time', 'datetime', 'timestamp', '采集时间'])
            temp_col = _find_col(df, ['温度', '温度值', 'temp', 'temperature', '车厢温度'])

            for _, row in df.iterrows():
                try:
                    plate = str(row[plate_col]).strip()
                    ts = pd.to_datetime(row[time_col])
                    temp = float(row[temp_col])
                    if pd.isna(ts) or pd.isna(temp):
                        continue
                    records.append(TemperatureRecord(
                        plate_number=plate,
                        record_time=ts.to_pydatetime(),
                        temperature=temp
                    ))
                except Exception:
                    continue
        except Exception as e:
            print(f"[警告] 读取温度文件失败 {os.path.basename(fp)}: {e}")
    return records


def parse_waybills(folder: str, standards: Dict[Tuple[str, str], CustomerStandard]) -> List[Waybill]:
    waybills: List[Waybill] = []
    patterns = ['*.csv', '*.txt', '*.xlsx', '*.xls']
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(folder, pat)))
    files = sorted(set(files))

    for fp in files:
        try:
            df = _read_any_table(fp)
            wb_col = _find_col(df, ['运单号', '运单编号', 'waybill', 'waybill_no', '单号'])
            plate_col = _find_col(df, ['车牌', '车牌号', 'plate', 'plate_number', '车号'])
            cust_col = _find_col(df, ['客户', '客户名称', 'customer', '收货方'])
            meat_col = _find_col(df, ['肉品', '肉品类', '肉品类型', 'meat_type', '品类', '货物'])
            load_col = _find_col(df, ['装车时间', '装货时间', 'load_time', '发车时间', '出发时间'])
            unload_col = _find_col(df, ['卸货时间', '到货时间', 'unload_time', '到达时间', '送达时间'])

            for _, row in df.iterrows():
                try:
                    wb_no = str(row[wb_col]).strip()
                    plate = str(row[plate_col]).strip()
                    customer = str(row[cust_col]).strip()
                    meat_type = str(row[meat_col]).strip()
                    load_t = pd.to_datetime(row[load_col]).to_pydatetime()
                    unload_t = pd.to_datetime(row[unload_col]).to_pydatetime()

                    std = standards.get((customer, meat_type))
                    if std:
                        tmin = std.temp_min
                        tmax = std.temp_max
                        pre_cool_req = std.pre_cool_required
                        pre_cool_t = std.pre_cool_temp
                        cont_ot = std.continuous_overtemp_minutes
                    else:
                        tmin = -18.0
                        tmax = -10.0
                        pre_cool_req = True
                        pre_cool_t = -10.0
                        cont_ot = 10

                    waybills.append(Waybill(
                        waybill_no=wb_no,
                        plate_number=plate,
                        customer=customer,
                        meat_type=meat_type,
                        load_time=load_t,
                        unload_time=unload_t,
                        target_temp_min=tmin,
                        target_temp_max=tmax,
                        pre_cool_required=pre_cool_req,
                        pre_cool_temp=pre_cool_t,
                        continuous_overtemp_minutes=cont_ot
                    ))
                except Exception:
                    continue
        except Exception as e:
            print(f"[警告] 读取运单文件失败 {os.path.basename(fp)}: {e}")
    return waybills


def parse_standards(folder: str) -> Dict[Tuple[str, str], CustomerStandard]:
    standards: Dict[Tuple[str, str], CustomerStandard] = {}
    patterns = ['*.csv', '*.txt', '*.xlsx', '*.xls']
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(folder, pat)))
    files = sorted(set(files))

    for fp in files:
        try:
            df = _read_any_table(fp)
            cust_col = _find_col(df, ['客户', '客户名称', 'customer'])
            meat_col = _find_col(df, ['肉品', '肉品类', '肉品类型', 'meat_type', '品类'])
            tmin_col = _find_col(df, ['最低温', '温度下限', 'temp_min', '最低温度'])
            tmax_col = _find_col(df, ['最高温', '温度上限', 'temp_max', '最高温度'])

            pre_cool_req_col = None
            pre_cool_temp_col = None
            cont_ot_col = None

            for c in df.columns:
                cl = c.lower()
                if '预冷' in c or 'pre_cool' in cl:
                    if '温度' in c or 'temp' in cl:
                        pre_cool_temp_col = c
                    else:
                        pre_cool_req_col = c
                if '连续超温' in c or 'continuous' in cl:
                    cont_ot_col = c

            for _, row in df.iterrows():
                try:
                    customer = str(row[cust_col]).strip()
                    meat_type = str(row[meat_col]).strip()
                    tmin = float(row[tmin_col])
                    tmax = float(row[tmax_col])

                    pre_cool_req = True
                    if pre_cool_req_col:
                        val = str(row[pre_cool_req_col]).strip().lower()
                        pre_cool_req = val in ('是', 'yes', 'true', '1', '需要', 'required')

                    pre_cool_t = tmax
                    if pre_cool_temp_col:
                        try:
                            pre_cool_t = float(row[pre_cool_temp_col])
                        except Exception:
                            pre_cool_t = tmax

                    cont_ot = 10
                    if cont_ot_col:
                        try:
                            cont_ot = int(row[cont_ot_col])
                        except Exception:
                            cont_ot = 10

                    std = CustomerStandard(
                        customer=customer,
                        meat_type=meat_type,
                        temp_min=tmin,
                        temp_max=tmax,
                        pre_cool_required=pre_cool_req,
                        pre_cool_temp=pre_cool_t,
                        continuous_overtemp_minutes=cont_ot
                    )
                    standards[(customer, meat_type)] = std
                except Exception:
                    continue
        except Exception as e:
            print(f"[警告] 读取温区标准文件失败 {os.path.basename(fp)}: {e}")
    return standards
