import os
import sys
import csv
import click
from datetime import datetime, date
from typing import List, Optional

from .parsers import parse_temperature_files, parse_waybills, parse_standards
from .matcher import match_waybills_with_temps
from .checker import audit_all
from .reporter import (
    print_summary, generate_audit_files,
    generate_daily_report, export_review_csv
)
from .models import Waybill, AuditResult


def _filter_waybills(
    waybills: List[Waybill],
    target_date: str = None,
    customer: str = None,
    meat_type: str = None
) -> List[Waybill]:
    filtered = waybills

    if target_date:
        try:
            d = date.fromisoformat(target_date)
            filtered = [
                w for w in filtered
                if w.load_time.date() == d or w.unload_time.date() == d
            ]
        except ValueError:
            click.echo(f"[错误] 日期格式不正确，请使用 YYYY-MM-DD 格式", err=True)
            sys.exit(1)

    if customer:
        filtered = [
            w for w in filtered
            if customer.lower() in w.customer.lower()
        ]

    if meat_type:
        filtered = [
            w for w in filtered
            if meat_type.lower() in w.meat_type.lower()
        ]

    return filtered


@click.group()
def cli():
    """肉类冷链温区稽核工具 - 批量检查运输温度合规性"""
    pass


@cli.command()
@click.option(
    '--input-dir', '-i',
    type=click.Path(file_okay=False, dir_okay=True),
    default='./data',
    show_default=True,
    help='输入数据目录，包含 temperature、waybills、standards 三个子文件夹'
)
@click.option(
    '--output-dir', '-o',
    type=click.Path(file_okay=False, dir_okay=True),
    default='./output',
    show_default=True,
    help='稽核摘要文件输出目录'
)
@click.option(
    '--date', '-d',
    type=str,
    default=None,
    help='只检查指定日期的运单，格式：YYYY-MM-DD'
)
@click.option(
    '--customer', '-c',
    type=str,
    default=None,
    help='只检查指定客户的运单（支持模糊匹配）'
)
@click.option(
    '--meat-type', '-m',
    type=str,
    default=None,
    help='只检查指定肉品类型的运单（支持模糊匹配）'
)
@click.option(
    '--abnormal-only', is_flag=True,
    help='只输出异常运单的摘要文件'
)
def check(input_dir, output_dir, date, customer, meat_type, abnormal_only):
    """执行冷链温区稽核检查

    将温度记录仪文件、运单清单、客户温区标准分别放入指定目录的
    temperature/、waybills/、standards/ 子文件夹中，运行本命令即可自动稽核。
    """
    temp_dir = os.path.join(input_dir, 'temperature')
    waybill_dir = os.path.join(input_dir, 'waybills')
    standard_dir = os.path.join(input_dir, 'standards')

    for d_name, d_path in [
        ('温度记录', temp_dir),
        ('运单清单', waybill_dir),
        ('温区标准', standard_dir)
    ]:
        if not os.path.isdir(d_path):
            click.echo(f"[错误] 找不到{d_name}目录: {d_path}", err=True)
            sys.exit(1)

    click.echo(f"正在读取数据...")
    click.echo(f"  温度记录目录: {temp_dir}")
    click.echo(f"  运单清单目录: {waybill_dir}")
    click.echo(f"  温区标准目录: {standard_dir}")

    standards = parse_standards(standard_dir)
    click.echo(f"  ✓ 读取到 {len(standards)} 条客户温区标准")

    waybills = parse_waybills(waybill_dir, standards)
    click.echo(f"  ✓ 读取到 {len(waybills)} 条运单")

    temp_records = parse_temperature_files(temp_dir)
    wb_no_count = sum(1 for r in temp_records if r.waybill_no)
    click.echo(f"  ✓ 读取到 {len(temp_records)} 条温度记录 (含运单号 {wb_no_count} 条)")

    filtered = _filter_waybills(waybills, date, customer, meat_type)
    if date or customer or meat_type:
        click.echo(f"  筛选后运单: {len(filtered)} 条")

    if not filtered:
        click.echo("\n[提示] 没有符合条件的运单数据。")
        return

    click.echo("\n正在匹配温度数据与运单...")
    matched = match_waybills_with_temps(filtered, temp_records)
    matched_count = sum(1 for v in matched.values() if v)
    click.echo(f"  ✓ 成功匹配 {matched_count}/{len(filtered)} 票运单的温度数据")

    click.echo("\n正在执行稽核检查...")
    results = audit_all(filtered, matched)

    print_summary(results)

    generate_audit_files(results, output_dir)
    click.echo(f"\n稽核摘要文件已生成到: {os.path.abspath(output_dir)}")

    report_path = generate_daily_report(results, output_dir)
    if report_path:
        click.echo(f"汇总日报已生成:\n  {report_path}")

    if abnormal_only:
        abnormal_results = [r for r in results if r.is_abnormal]
        if abnormal_results:
            generate_audit_files(abnormal_results, output_dir)
            click.echo(f"异常运单摘要已重新生成 ({len(abnormal_results)} 票)")

    review_path = export_review_csv(results, output_dir)
    click.echo(f"复核交接单已生成: {review_path}")


@cli.command()
@click.option(
    '--output-dir', '-o',
    type=click.Path(file_okay=False, dir_okay=True),
    default='./data',
    show_default=True,
    help='模板文件输出目录'
)
@click.option(
    '--with-sample', is_flag=True,
    help='同时生成示例数据文件，方便培训新人'
)
def template(output_dir, with_sample):
    """生成空白模板文件，质检员照着填就能跑

    在指定目录下生成 temperature/、waybills/、standards/ 三个子文件夹，
    每个文件夹中放入带列头的空白 CSV 模板。
    加 --with-sample 时额外生成带示例数据的文件。
    """

    temp_dir = os.path.join(output_dir, 'temperature')
    wb_dir = os.path.join(output_dir, 'waybills')
    std_dir = os.path.join(output_dir, 'standards')

    for d in [temp_dir, wb_dir, std_dir]:
        os.makedirs(d, exist_ok=True)

    std_template = os.path.join(std_dir, '客户温区标准_模板.csv')
    with open(std_template, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['客户', '肉品', '最低温', '最高温', '预冷要求', '预冷温度', '连续超温判定(分钟)'])
    click.echo(f"  ✓ {std_template}")

    wb_template = os.path.join(wb_dir, '运单清单_模板.csv')
    with open(wb_template, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['运单号', '车牌', '客户', '肉品', '装车时间', '卸货时间'])
    click.echo(f"  ✓ {wb_template}")

    temp_template = os.path.join(temp_dir, '温度记录_模板.csv')
    with open(temp_template, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['车牌', '时间', '温度', '运单号'])
    click.echo(f"  ✓ {temp_template}")

    click.echo(f"\n空白模板已生成到: {os.path.abspath(output_dir)}")
    click.echo("质检员按列头填入数据后，运行 audit check 即可稽核。")

    if with_sample:
        click.echo("\n正在生成示例数据...")

        std_sample = os.path.join(std_dir, '客户温区标准_示例.csv')
        with open(std_sample, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['客户', '肉品', '最低温', '最高温', '预冷要求', '预冷温度', '连续超温判定(分钟)'])
            writer.writerow(['大润发', '冷鲜猪肉', 0, 4, '是', 4, 15])
            writer.writerow(['大润发', '冷冻牛肉', -18, -10, '是', -10, 10])
            writer.writerow(['沃尔玛', '冷鲜猪肉', 0, 4, '是', 4, 15])
            writer.writerow(['沃尔玛', '冷冻鸡肉', -18, -10, '是', -10, 10])
        click.echo(f"  ✓ {std_sample}")

        wb_sample = os.path.join(wb_dir, '运单清单_示例.csv')
        with open(wb_sample, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['运单号', '车牌', '客户', '肉品', '装车时间', '卸货时间'])
            writer.writerow(['YD20250620001', '沪A12345', '大润发', '冷鲜猪肉', '2025-06-20 06:30:00', '2025-06-20 09:15:00'])
            writer.writerow(['YD20250620002', '沪B67890', '沃尔玛', '冷冻牛肉', '2025-06-20 07:00:00', '2025-06-20 10:45:00'])
        click.echo(f"  ✓ {wb_sample}")

        temp_sample = os.path.join(temp_dir, '温度记录_示例.csv')
        with open(temp_sample, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['车牌', '时间', '温度', '运单号'])
            writer.writerow(['沪A12345', '2025-06-20 06:00:00', 3.5, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 06:30:00', 3.2, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 07:00:00', 2.3, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 07:30:00', 1.5, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 08:00:00', 0.8, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 08:30:00', 2.0, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 09:00:00', 3.2, 'YD20250620001'])
            writer.writerow(['沪A12345', '2025-06-20 09:15:00', 3.6, 'YD20250620001'])
            writer.writerow(['沪B67890', '2025-06-20 06:30:00', -12.0, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 07:00:00', -12.0, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 07:30:00', -11.0, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 08:00:00', -9.5, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 08:30:00', -7.5, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 09:00:00', -6.5, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 09:30:00', -5.5, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 10:00:00', -6.0, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 10:30:00', -10.0, 'YD20250620002'])
            writer.writerow(['沪B67890', '2025-06-20 10:45:00', -11.5, 'YD20250620002'])
        click.echo(f"  ✓ {temp_sample}")

        click.echo("\n示例数据已生成！新人可以先看示例理解格式，")
        click.echo("再用模板新建自己的数据文件。")
        click.echo("运行 audit check -i <目录> 即可对示例数据执行稽核。")


@cli.command()
@click.option(
    '--input-dir', '-i',
    type=click.Path(file_okay=False, dir_okay=True),
    default='./data',
    show_default=True,
    help='输入数据目录'
)
@click.option(
    '--output-dir', '-o',
    type=click.Path(file_okay=False, dir_okay=True),
    default='./output',
    show_default=True,
    help='复核交接单输出目录'
)
@click.option(
    '--date', '-d',
    type=str,
    default=None,
    help='只导出指定日期的运单'
)
@click.option(
    '--customer', '-c',
    type=str,
    default=None,
    help='只导出指定客户的运单'
)
@click.option(
    '--meat-type', '-m',
    type=str,
    default=None,
    help='只导出指定肉品类型的运单'
)
@click.option(
    '--status', '-s',
    type=click.Choice(['待复核', '已确认', '已放行']),
    default=None,
    help='只导出指定复核状态的运单'
)
def review(input_dir, output_dir, date, customer, meat_type, status):
    """导出复核交接单，供主管签字确认

    先运行 audit check 完成稽核后，用本命令导出复核交接单。
    异常运单默认标记为"待复核"，质检员可修改 CSV 中的复核状态
    为"已确认"或"已放行"后重新导入。
    """
    temp_dir = os.path.join(input_dir, 'temperature')
    waybill_dir = os.path.join(input_dir, 'waybills')
    standard_dir = os.path.join(input_dir, 'standards')

    for d_name, d_path in [
        ('温度记录', temp_dir),
        ('运单清单', waybill_dir),
        ('温区标准', standard_dir)
    ]:
        if not os.path.isdir(d_path):
            click.echo(f"[错误] 找不到{d_name}目录: {d_path}", err=True)
            sys.exit(1)

    click.echo("正在读取数据并执行稽核...")

    standards = parse_standards(standard_dir)
    waybills = parse_waybills(waybill_dir, standards)
    temp_records = parse_temperature_files(temp_dir)

    filtered = _filter_waybills(waybills, date, customer, meat_type)
    if not filtered:
        click.echo("[提示] 没有符合条件的运单数据。")
        return

    matched = match_waybills_with_temps(filtered, temp_records)
    results = audit_all(filtered, matched)

    generate_audit_files(results, output_dir)

    if status:
        results = [r for r in results if r.review_status == status or (status == "待复核" and r.is_abnormal and r.review_status == "待复核")]

    filepath = export_review_csv(results, output_dir)
    click.echo(f"\n复核交接单已导出: {filepath}")
    click.echo('质检员可在 CSV 中将复核状态改为"已确认"或"已放行"，再交给主管签字。')

    abnormal_count = sum(1 for r in results if r.is_abnormal)
    total_count = len(results)
    click.echo(f"共 {total_count} 票运单，其中 {abnormal_count} 票异常待复核。")


if __name__ == '__main__':
    cli()
