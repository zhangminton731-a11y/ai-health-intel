import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from classify_content import classify_content

class ClassificationTests(unittest.TestCase):
    def test_paper_is_research_with_validation_stage(self):
        result=classify_content('External validation of clinical AI', '', '期刊论文')
        self.assertIn('papers', result['categories']['research'])
        self.assertIn('validation', result['stages'])
        self.assertNotIn('industry', result['sections'])

    def test_funding_is_business_not_research(self):
        result=classify_content('Medical AI startup raises Series A funding', '', '专业媒体')
        self.assertEqual(['industry'], result['sections'])
        self.assertIn('business', result['categories']['industry'])

    def test_policy_is_not_a_clinical_paper(self):
        result=classify_content('关于医学人工智能研究数据管理的政策通知', '', '专业媒体')
        self.assertEqual(['policy'],result['categories']['research'])
        self.assertIn('regulation',result['categories']['industry'])

    def test_open_dataset_is_method_and_data_stage(self):
        result=classify_content('Open-source clinical dataset for AI', '', '研究机构')
        self.assertIn('methods',result['categories']['research'])
        self.assertIn('data',result['stages'])

    def test_ring_launch_is_industry_product(self):
        result=classify_content('Wearable smart ring launches sleep tracking', '', '企业发布')
        self.assertEqual(['industry'],result['sections'])
        self.assertIn('products',result['categories']['industry'])

    def test_one_item_may_serve_both_audiences(self):
        result=classify_content('Company launches open-source clinical AI model', '', '企业发布')
        self.assertEqual(['research','industry'],result['sections'])

    def test_word_fragments_do_not_match_ai_or_ipo(self):
        result=classify_content('Hospital explains daily multidisciplinary work', '', '专业媒体')
        self.assertNotIn('technology',result['categories'].get('industry',[]))
        self.assertNotIn('business',result['categories'].get('industry',[]))

    def test_product_designation_is_not_policy_change(self):
        result=classify_content('FDA grants breakthrough designation to medical AI device', '', '专业媒体')
        self.assertNotIn('policy',result['categories'].get('research',[]))
        self.assertIn('regulation',result['categories']['industry'])
