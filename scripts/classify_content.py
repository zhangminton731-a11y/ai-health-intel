"""Route current content by audience and task; labels are not evidence ratings."""
import re

POLICY = ('policy', 'policies', 'regulation', 'guidance',
          'research grant', '政策', '科研资助', '申报', '征求意见', '伦理')
METHODS = ('dataset', 'datasets', 'open-source', 'open source', 'benchmark',
           'large language model', 'large language models', 'clinical validation', 'clinical study',
           '研究方法', '数据集', '开源', '算法', '模型验证', '数据处理', '研究工具')
INDUSTRY = {
    'products': ('launch', 'launches', 'unveils', 'new feature', 'product', 'device', 'app', 'platform', '推出', '产品', '新品', '功能', '方案'),
    'technology': ('ai', 'artificial intelligence', 'model', 'models', 'algorithm', 'software', 'robotics', '人工智能', '模型', '算法', '技术'),
    'business': ('raises', 'funding', 'series a', 'series b', 'series c', 'ipo', 'acquisition', 'acquires', 'merger', 'partnership', '融资', '并购', '收购', '合作', '订单', '渠道'),
    'regulation': POLICY + ('regulatory', 'fda', 'clearance', 'ce mark', '监管', '审批', '获批'),
}
STAGES = {
    'design': ('study design', 'protocol', 'cohort', '研究设计', '队列', '研究方案'),
    'data': ('data', 'dataset', 'datasets', 'annotation', 'electronic health record', '数据', '标注', '病历'),
    'analysis': ('model', 'models', 'algorithm', 'algorithms', 'prediction', 'machine learning', '模型', '算法', '预测', '分析'),
    'validation': ('validation', 'evaluation', 'trial', 'benchmark', 'external validation', '验证', '评价', '评估', '试验'),
}

def contains(text: str, terms: tuple) -> bool:
    return any(re.search(r'(?<![a-z])'+re.escape(term)+r'(?![a-z])',text) for term in terms)

def classify_content(title: str, summary: str, source_type: str) -> dict:
    text=(title+' '+summary).lower()
    research=[]
    paper=source_type=='期刊论文'
    if paper:research.append('papers')
    if contains(text,METHODS):research.append('methods')
    if not paper and contains(text,POLICY):research.append('policy')
    # A paper mentioning funding or a model is not automatically business news.
    industry=[] if paper else [key for key,terms in INDUSTRY.items() if contains(text,terms)]
    if not research and not industry:industry=['technology'] if source_type=='企业发布' else ['overview']
    categories={}
    if research:categories['research']=research
    if industry:categories['industry']=industry
    return {'sections':list(categories),'categories':categories,
            'stages':[key for key,terms in STAGES.items() if contains(text,terms)] if research else []}
