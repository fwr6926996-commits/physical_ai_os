"""Read-only arithmetic/integrity audit; never executes the suite or imports it."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/phase5a/t0/T0-L-20261027-01'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda name: json.loads((OUT / name).read_text())
readlines = lambda name: [json.loads(x) for x in (OUT / name).read_text().splitlines()]


def main():
    for name, digest in load('hashes.json').items():
        assert sha(OUT / name) == digest, name
    manifest = load('run_manifest.json')
    for name, digest in manifest['source_sha256'].items():
        assert sha(ROOT / name) == digest, name
    events, commands, fixtures = [readlines(n) for n in (
        'events.jsonl', 'mock_commands.jsonl', 'verifier_inputs.jsonl')]
    assert len(events) + sum(len(f['events']) for f in fixtures) <= 512
    assert sum(p.stat().st_size for p in OUT.iterdir()) <= 1048576
    assert all(len(line.encode()) <= 16384 for n in ('events.jsonl', 'mock_commands.jsonl', 'verifier_inputs.jsonl')
               for line in (OUT / n).read_text().splitlines())
    case_ids = {e['case_id'] for e in events}
    assert len(case_ids) == 34
    assert [c['case_id'] for c in commands] == ['T0-01', 'T0-09']
    windows = []
    for cid in sorted(case_ids):
        es = [e for e in events if e['case_id'] == cid]
        cs = [c for c in commands if c['case_id'] == cid]
        assert [e['sequence'] for e in es] == list(range(len(es)))
        rejections = [e for e in es if e['type'] == 'ACTION_REJECTED']
        assert not {e['token_key'] for e in rejections} & {c['token_key'] for c in cs}
        for e in rejections:
            assert {'checked_at', 'valid_until', 'token_key', 'reason', 'expired_drop_count'} <= e.keys()
        for e in es:
            if e['type'] != 'TIME_CHECK':
                continue
            p, r = e['points'], e['result']
            if r['age_available']:
                now = int(p.get('sink_attempt_at', p['now'])['timestamp'])
                assert int(r['action_age_ns']) == now - int(p['generated_at']['timestamp'])
                assert int(r['observation_age_ns']) == now - int(p['observation']['timestamp'])
            else:
                assert r['action_age_ns'] is None and r['observation_age_ns'] is None
        if any(e['type'] == 'WINDOW_START' for e in es):
            ticks = [int(e['timestamp_ns']) for e in es if e['type'] == 'CONSUMER_TICK']
            assert ticks == list(range(120000000, 340000000, 20000000))
            assert es[0]['type'] == 'WINDOW_START' and int(es[0]['timestamp_ns']) == 120000000
            assert [e['type'] for e in es[-3:]] == ['WINDOW_END', 'SINK_FINAL_COUNT', 'RECORDER_STATS']
            assert int(es[-3]['timestamp_ns']) == 340000000
            assert es[-3]['close_reason'] == 'NORMAL_END'
            assert es[0]['sink_count'] == es[-2]['sink_count'] == 0 and not cs
            assert es[-1]['loss_count'] == 0 and es[-1]['recorded_event_count'] == len(es)
            assert len(rejections) == 1 and rejections[0]['reason'] == 'EXPIRED'
            assert rejections[0]['checked_at']['timestamp'] == '120000000'
            assert rejections[0]['valid_until']['timestamp'] == '100000000'
            assert es[-2]['expired_drop_count'] == rejections[0]['expired_drop_count'] == 1
            windows.append({'case_id': cid, 'ticks': len(ticks), 'commands': len(cs), 'expired_drop': 1})
    sink_checks = [e for e in events if e['case_id'] == 'T0-15' and e['type'] == 'TIME_CHECK']
    assert [e['result']['decision'] for e in sink_checks] == ['ALLOW', 'REJECT']
    assert sink_checks[1]['result']['reason'] == 'EXPIRED'
    assert not [c for c in commands if c['case_id'] == 'T0-15']
    summary = load('evidence_summary.json')
    assert len(summary['cases']) == 34 and all(c['matches_expected'] for c in summary['cases'])
    assert len(windows) == 6
    return {'status': 'PASS_READ_ONLY_RAW_AUDIT', 'suite_rerun': False,
            'case_count': len(case_ids), 'actual_event_count': len(events),
            'constructed_fixture_event_count': sum(len(f['events']) for f in fixtures),
            'actual_commands': len(commands), 'actual_stop_windows': windows,
            'total_output_bytes': sum(p.stat().st_size for p in OUT.iterdir()),
            'audit_script_sha256': sha(Path(__file__))}


if __name__ == '__main__':
    print(json.dumps(main(), ensure_ascii=False, indent=2))
