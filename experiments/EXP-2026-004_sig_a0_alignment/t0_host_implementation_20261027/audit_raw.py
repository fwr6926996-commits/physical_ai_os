"""Read-only stdlib audit of formal T0-H artifacts; does not execute workers."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'artifacts/phase5a/t0_host/T0-H-20261027-01'
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
load = lambda p: json.loads(p.read_text())
rows = lambda p: [json.loads(x) for x in p.read_text().splitlines()]


def main():
    hashes = load(OUT / 'hashes.json')
    for name, digest in hashes.items():
        assert sha(OUT / name) == digest, name
    manifest = load(OUT / 'run_manifest.json')
    for name, digest in manifest['source_sha256'].items():
        assert sha(ROOT / name) == digest, name
    total = sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    jsonl_paths = list(OUT.rglob('*.jsonl'))
    physical_lines = sum(len(rows(p)) for p in jsonl_paths)
    assert total <= 2097152 and physical_lines <= 1024
    max_line = max(len(x) + 1 for p in jsonl_paths for x in p.read_bytes().splitlines())
    assert max_line <= 16384
    parent = rows(OUT / 'supervisor_events.jsonl')
    assert [e['sequence'] for e in parent] == list(range(len(parent)))
    alive, maximum = {}, 0
    for e in parent:
        if e['type'] == 'CHILD_STARTED':
            key = (e['pid'], e['process_starttime'])
            assert key not in alive
            alive[key] = e['instance_id']
            maximum = max(maximum, len(alive))
            assert e['active_workers'] == len(alive) <= 2
        elif e['type'] == 'CHILD_EXITED':
            assert alive.pop((e['pid'], e['process_starttime'])) == e['instance_id']
            assert e['active_workers'] == len(alive) and e['exit_code'] == 0
    assert not alive and maximum == 2 and parent[-1]['active_children'] == 0
    inventory = load(OUT / 'process_inventory.json')
    assert len(inventory) == 20
    for inst in inventory:
        stat = Path(f"/proc/{inst['pid']}/stat")
        if stat.exists():
            assert stat.read_text().rsplit(')', 1)[1].split()[19] != inst['process_starttime'], 'original worker still exists'
    bindings = rows(OUT / 'binding_observations.jsonl')
    assert len(bindings) == 40
    for b in bindings:
        r, o, p = b['reported'], b['observed'], b['supervisor']
        fields = {k: p[k] for k in ('boot_id_sha256','namespace_dev','namespace_ino','clock_id_symbol')}
        expected = 'linux-monotonic:' + hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        assert b['source'] == expected
        assert o['ppid'] == p['pid']
        for key in ('boot_id_sha256','namespace_dev','namespace_ino','timens_offsets'):
            assert o[key] == p[key]
        if b['reason'] is None:
            assert r == o
    commands = rows(OUT / 'mock_commands.jsonl')
    assert [c['case_id'] for c in commands] == ['H-01','H-08']
    windows, sink_recheck = [], None
    for inst in inventory:
        if inst['role'] != 'executor':
            continue
        base = OUT / inst['relative_directory']
        events, sink = rows(base / 'events.jsonl'), rows(base / 'mock_commands.jsonl')
        assert [e['sequence'] for e in events] == list(range(len(events)))
        assert events[-1]['type'] == 'EXIT_NORMAL'
        rejects = [e for e in events if e['type'] == 'ACTION_REJECTED']
        assert not {r['token_key'] for r in rejects} & {c['token_key'] for c in sink}
        for e in events:
            if e['type'] == 'TIME_CHECK':
                points, result = e['points'], e['result']
                if result['age_available']:
                    now = int(points.get('sink_attempt_at', points['now'])['timestamp'])
                    assert int(result['action_age_ns']) == now - int(points['generated_at']['timestamp'])
                    assert int(result['observation_age_ns']) == now - int(points['observation']['timestamp'])
                else:
                    assert result['action_age_ns'] is None and result['observation_age_ns'] is None
            if e['type'] == 'MOCK_COMMAND_COMMITTED':
                assert e['command'] in sink
                assert int(e['command']['at']['timestamp']) <= int(e['at']['timestamp']) < int(e['command']['valid_until']['timestamp'])
        if inst['case_id'] in ('H-06','H-07'):
            start = next(e for e in events if e['type'] == 'WINDOW_START')
            end = next(e for e in events if e['type'] == 'WINDOW_END')
            count = next(e for e in events if e['type'] == 'SINK_FINAL_COUNT')
            stats = next(e for e in events if e['type'] == 'RECORDER_STATS')
            t0, t1 = int(start['at']['timestamp']), int(end['at']['timestamp'])
            ticks = [e for e in events if e['type'] == 'CONSUMER_TICK']
            assert [t['slot'] for t in ticks] == list(range(10)) and t1 >= t0 + 200000000
            for slot,tick in enumerate(ticks):
                assert t0 + slot*20000000 <= int(tick['at']['timestamp']) < t0 + (slot+1)*20000000
                assert tick['empty'] is True
            assert len(rejects) == 1 and rejects[0]['reason'] == 'EXPIRED'
            assert int(rejects[0]['checked_at']['timestamp']) >= int(rejects[0]['valid_until']['timestamp'])
            assert rejects[0]['sequence'] < start['sequence'] and rejects[0]['token_key'] == start['token_key']
            assert start['expired_drop_count'] == count['expired_drop_count'] == rejects[0]['expired_drop_count'] == 1
            assert start['sink_count'] == count['sink_count'] == 0 and not sink
            assert stats['loss_count'] == 0 and stats['recorded_event_count'] == stats['sequence'] + 1
            assert end['close_reason'] == 'NORMAL_END'
            windows.append({'case_id':inst['case_id'],'duration_ns':str(t1-t0),'ticks':10,'mock_commands':0,'expired_drop':1,'maximum_tick_lateness_ns':max(int(t['lateness_ns']) for t in ticks)})
            if inst['case_id'] == 'H-07':
                checks = [e for e in events if e['type'] == 'TIME_CHECK']
                assert [e['result']['decision'] for e in checks] == ['ALLOW','REJECT']
                sink_recheck = {'initial_age_ns': checks[0]['result']['action_age_ns'], 'sink_age_ns': checks[1]['result']['action_age_ns']}
        if inst['case_id'] == 'H-08' and '-g1-' in inst['instance_id']:
            old = next(e for e in events if e['type'] == 'TIME_CHECK' and e['result'].get('reason') == 'SESSION_MISMATCH')
            assert int(old['points']['now']['timestamp']) < int(old['points']['valid_until']['timestamp'])
            assert old['points']['generated_at']['source'] == old['points']['now']['source']
            assert old['points']['generated_at']['session_id'] != old['points']['now']['session_id']
    summary = load(OUT / 'evidence_summary.json')
    assert len(summary['cases']) == 12 and all(c['matches_expected'] for c in summary['cases'])
    assert len(windows) == 2
    return {'status':'PASS_READ_ONLY_RAW_AUDIT','suite_rerun':False,'source_and_artifact_hashes_valid':True,'maximum_owned_processes':maximum+1,'all_owned_workers_exited':True,'worker_instances':len(inventory),'binding_observations':len(bindings),'actual_commands':len(commands),'stop_windows':windows,'H_07_recheck':sink_recheck,'total_output_bytes':total,'maximum_jsonl_line_bytes':max_line,'physical_jsonl_line_count_including_aggregates':physical_lines,'audit_script_sha256':sha(Path(__file__))}


if __name__ == '__main__':
    print(json.dumps(main(),ensure_ascii=False,indent=2))
