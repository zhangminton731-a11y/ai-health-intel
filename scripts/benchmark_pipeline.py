"""Reproducible scheduling comparison with fixed, explicitly synthetic I/O."""
import json
import statistics
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'engine/src'))
from sih_ref.pipeline import run_pipeline
from sih_ref.sources import SourceResult


def measure():
    def collect(source, **kwargs):
        time.sleep(0.05)
        return SourceResult(source['id'], 'ok', [{'title':'Clinical AI validation',
            'summary':'Synthetic clinical methods example, not a real article.',
            'url':'https://example.org/'+source['id'], 'published_at':'2026-10-04'}])
    results, facts = {}, []
    with tempfile.TemporaryDirectory() as td, patch('sih_ref.pipeline.collect_source', side_effect=collect):
        root = Path(td)
        for workers in (1, 4):
            samples = []
            config = root/'sources.json'
            config.write_text(json.dumps({'collection_workers':workers, 'sources':[
                {'id':str(i),'kind':'rss','enabled':True} for i in range(8)]}))
            for run in range(5):
                output = root/f'{workers}-{run}'
                start = time.perf_counter()
                run_pipeline(config_path=config, profile_path=ROOT/'config/profile.json',
                    output_dir=output, as_of=date(2026,10,4), live=True, stateless=True, deterministic=True)
                samples.append((time.perf_counter()-start)*1000)
                facts.append((output/'daily_items.jsonl').read_bytes())
            results[str(workers)] = {'median_ms':round(statistics.median(samples),2), 'samples_ms':[round(s,2) for s in samples]}
    assert all(f == facts[0] for f in facts), 'Concurrent collection changed the facts'
    return {'kind':'synthetic scheduling benchmark', 'sources':8, 'delay_per_source_ms':50,
            'identical_facts':True, 'results':results,
            'reduction_percent':round(100*(1-results['4']['median_ms']/results['1']['median_ms']),1)}


if __name__ == '__main__':
    print(json.dumps(measure(), indent=2))
