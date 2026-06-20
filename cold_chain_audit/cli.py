import os
import sys
import click
from datetime import datetime, date
from typing import List

from .parsers import parse_temperature_files, parse_waybills, parse_standards
from .matcher import match_waybills_with_temps
from .checker import audit_all
from .reporter import print_summary, generate_audit_files
from .models import Waybill


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


@click.command()
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
def main(input_dir, output_dir, date, customer, meat_type, abnormal_only):
    """肉类冷链温区稽核工具 - 批量检查运输温度合规性

    将温度记录仪文件、运单清单、客户温区标准分别放入指定目录的
    temperature/、waybills/、standards/ 子文件夹中，运行本工具即可自动稽核。
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
    click.echo(f"  ✓ 读取到 {len(temp_records)} 条温度记录")

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

    output_results = results
    if abnormal_only:
        output_results = [r for r in results if r.is_abnormal]

    if output_results:
        files = generate_audit_files(output_results, output_dir)
        click.echo(f"\n稽核摘要文件已生成到: {os.path.abspath(output_dir)}")
        click.echo(f"共生成 {len(files)} 个摘要文件")
    else:
        click.echo("\n没有需要输出的稽核结果。")


if __name__ == '__main__':
    main()
