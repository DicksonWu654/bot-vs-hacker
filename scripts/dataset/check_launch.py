#!/usr/bin/env python3
"""Read-only checks for the launch dataset's denominators and publication decisions."""
import json
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[2]
rows = json.loads((ROOT / 'data/incidents.json').read_text())
stats = json.loads((ROOT / 'data/headline_stats.json').read_text())
head = [r for r in rows if r['headline']]
assert (len(head), len({r['slug'] for r in head})) == (19, 15)
euler = next(r for r in rows if r['slug'] == 'euler-copybot-2023')
assert not euler['headline'] and euler['verdict'] == 'confirmed-onchain' and euler['evidence_strength'] == 'medium' and euler['caveat']
assert all(r['fate']['return_status'] in {'returned', 'partial', 'none', 'unknown'} for r in rows)
for slug, status in [('punk-2021','partial'),('transitswap-2022','returned'),('neemo-2025','returned')]:
    assert next(r for r in rows if r['slug'] == slug)['fate']['return_status'] == status
assert all(r['fate']['return_status'] == 'partial' for r in rows if r['slug'] == 'unizen-2024')

def check_return(selected, published):
    measured = [r for r in selected if r['loot'].get('scope') == 'bot-tx' and r['loot'].get('gross_loot_eth') and isinstance(r['fate'].get('returned_total_eth'), (int,float))]
    numerator = sum(r['fate']['returned_total_eth'] for r in measured)
    denominator = sum(r['loot']['gross_loot_eth'] for r in measured)
    assert published['rows'] == len(measured)
    assert published['known_zero_rows'] == sum(r['fate']['returned_total_eth'] == 0 for r in measured)
    assert abs(published['sum_returned_eth'] - numerator) < .0001
    assert abs(published['sum_denominator_eth'] - denominator) < .0001
    assert abs(published['pooled_pct'] - 100*numerator/denominator) < .00051
    return measured

measured = check_return(head, stats['loot']['returns']['gross']['headline_rows'])
assert {r['slug'] for r in measured if r['fate']['returned_total_eth'] == 0} == {'earningfarm-2022','shoco-2023','bifi-2026'}
c0 = [r for r in head if (r['bot'].get('eoa') or '').lower() == '0xc0ffeebabe5d496b2dde509f9fa189c25cf29671']
assert len(c0) == 4
for row in c0:
    order = row['public_ordering']
    target = next(t for t in row['attacker']['attack_txs'] if t['hash'] == order['raced_attacker_tx'])
    assert (order['attacker_block'], order['attacker_position']) == (target['block'], target['index'])
    assert (order['bot_block'], order['bot_position']) == (row['bot']['block'], row['bot']['position'])
    assert row['comparison_policy']
remaining = [r for r in head if r not in c0]
sensitivity = stats['sensitivity']['excluding_c0ffeebabe_rows']
assert (sensitivity['rows'], sensitivity['incidents']) == (15, 13)
check_return(remaining, sensitivity['loot']['returns']['gross']['headline_rows'])
mature = [r for r in head if r['era'] == 'mature-pbs-2024-26' and r['loot'].get('scope') == 'bot-tx' and r['loot'].get('gross_loot_eth')]
after = [(r['loot']['paid_to_block_producer_eth'] - r['loot']['builder_refund_to_bot_eth']) / r['loot']['gross_loot_eth'] * 100 for r in mature]
assert abs(median(after) - stats['block_producer_share']['by_era_headline']['mature-pbs-2024-26']['after_refunds']['median_row_pct']) < .001
assert {r['slug'] for r in mature if r['loot']['pct_to_builder'] < 2} == {'neemo-2025','kelp-rseth-2026','bifi-2026'}
print('launch data checks: 0 FAIL; headline 19/15; sensitivity 15/13; returns include 3 known zeros')
