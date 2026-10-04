from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from daily_digest import build_issues, issue_text, build_publication
from build_site import reader_summary


class DailyDigestTests(unittest.TestCase):
    today = date(2026, 9, 27)

    def test_publication_date_does_not_relabel_source_dates(self):
        rows = [self.row('yesterday', '2026-09-26'), self.row('old', '2026-09-20')]
        publication = build_publication(rows, self.today)
        self.assertEqual('2026-09-27', publication['date'])
        self.assertEqual(['yesterday'], publication['item_ids'])
        self.assertEqual(['2026-09-26'], publication['source_dates'])
        self.assertIn('2026-09-26', publication['text'])
        self.assertEqual([], build_publication([], self.today)['item_ids'])

    def row(self, id, day='2026-09-27', category='papers', score=50):
        return {'id':id,'date':day,'t':'医学研究 '+id,'te':'Medical research '+id,
                's':'来源给出的摘要','u':'https://example.org/'+id,'src':'Test journal',
                'categories':{'research':[category]},'rel':score,'freshness':'fresh','tier':'skim'}

    def test_date_groups_do_not_mix_days_or_fill_missing_days(self):
        rows=[self.row('today'),self.row('prior','2026-09-25'),self.row('old','2026-09-16'),self.row('future','2026-09-28')]
        issues=build_issues(rows,self.today)
        self.assertEqual(['2026-09-27','2026-09-25'],[e['date'] for e in issues])
        self.assertEqual(['today'],issues[0]['item_ids'])
        self.assertEqual(['prior'],issues[1]['item_ids'])

    def test_five_story_limit_diversity_duplicate_headlines_and_archive(self):
        rows=[self.row(str(i),score=i) for i in range(8)]+[self.row('policy',category='policy',score=0)]
        rows.append({**rows[7],'id':'duplicate','rel':-1})
        rows.append({**self.row('archive',score=99),'tier':'archive'})
        ids=build_issues(rows,self.today)[0]['item_ids']
        self.assertEqual(5,len(ids));self.assertEqual('policy',ids[0])
        self.assertIn('7',ids);self.assertNotIn('duplicate',ids);self.assertNotIn('archive',ids)

    def test_empty_and_reader_text_has_summary_sources_no_internal_stats_or_ad(self):
        self.assertEqual([],build_issues([],self.today))
        row=self.row('paper');edition=build_issues([row],self.today)[0]
        text=issue_text(edition,{'paper':row},self.today.isoformat())
        self.assertIn('来源给出的摘要',text);self.assertIn(row['u'],text)
        for word in ('事实池','推荐产出','运行正常','13028564458','TOP 10'):
            self.assertNotIn(word,text)
        self.assertIn('今日暂无新条目',issue_text(None,{},self.today.isoformat()))

    def test_title_only_items_do_not_become_empty_daily_stories(self):
        self.assertEqual([],build_issues([{**self.row('title-only'),'s':'','se':''}],self.today))

    def test_unstructured_abstract_keeps_late_results_as_whole_source_sentences(self):
        result = 'The full pipeline reached an AUROC of 0.952 in the external cohort.'
        limitation = 'Further validation is required before deployment.'
        source = 'Background information. '*60 + 'We propose a clinical framework. '+result+' '+limitation
        summary = reader_summary(source)
        self.assertIn(result, summary)
        self.assertIn(limitation, summary)
        self.assertIn('We propose a clinical framework.', summary)

    def test_abstract_preserves_findings_and_removes_encoded_markup(self):
        raw='&lt;strong&gt;Background:&lt;/strong&gt; Long background. Objective: Test AI. Methods: Cohort. Results: Accuracy was 80%. Conclusions: External validation is still needed.'
        summary=reader_summary(raw)
        self.assertIn('Accuracy was 80%.',summary)
        self.assertIn('External validation is still needed.',summary)
        self.assertNotIn('<strong>',summary)
        self.assertNotIn('Long background',summary)
        comparisons=reader_summary('Results: p &lt; 0.05 and score &gt; 0.8. Conclusions: Needs validation.')
        self.assertIn('p < 0.05 and score > 0.8.',comparisons)


if __name__ == '__main__':unittest.main()
