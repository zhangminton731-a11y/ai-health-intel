"""Reader reasons and a separate, dated 20-day reading archive."""
import json
from pathlib import Path
from sih_ref.core import score_item, freshness_gate

SUBJECTS = [
    (('parkinson', '帕金森'), '帕金森病'), (('sleep', 'apnea', '睡眠'), '睡眠与呼吸监测'),
    (('hypertension', 'blood pressure', '高血压'), '血压与慢病管理'),
    (('glucose', 'diabetes', '糖尿病'), '血糖管理'), (('cancer', 'tumor', 'oncolog', '肿瘤'), '肿瘤诊疗'),
    (('mental', 'psychiatr', '心理'), '精神心理健康'), (('stroke', '卒中'), '卒中研究'),
    (('imaging', 'radiolog', '影像'), '医学影像'), (('electronic health record', '病历'), '病历数据'),
    (('wearable', 'smart ring', 'watch', '可穿戴'), '可穿戴监测'),
    (('brain-computer', '脑机'), '脑机接口'), (('large language', 'llm', '大模型'), '医疗大模型'),
]

def reasons(item):
    text = (item.get('te', '')+' '+item.get('se', '')+' '+item.get('t', '')).lower()
    subject = next((label for terms,label in SUBJECTS if any(t in text for t in terms)), '')
    context = ('围绕'+subject+'，') if subject else '结合这篇文章的具体场景，'
    cats = item.get('categories', {})
    research = cats.get('research', [])
    industry = cats.get('industry', [])
    if 'policy' in research:
        r = context+'可先核对适用机构、实施时间与数据使用条件，判断是否影响你的课题方案和合作路径。'
    elif any(t in text for t in ('systematic review','meta-analysis','系统评价','荟萃')):
        r = context+'这类证据汇总适合用来查研究空白；重点看纳入人群、偏倚与结论一致性，再确定自己的临床问题。'
    elif any(t in text for t in ('retrospective','回顾性')):
        r = context+'可参考回顾性研究的入组和数据处理思路，评估手头病例是否适合开展类似课题；需核对混杂控制和外部验证。'
    elif any(t in text for t in ('randomized','randomised','随机')):
        r = context+'可关注干预、对照和终点如何设置，为自己的验证方案提供参照；研究结果能否迁移还取决于人群与场景。'
    elif 'methods' in research:
        r = context+'可评估这套方法的数据条件、复现资源和验证步骤，判断能否用于现有课题的分析环节。'
    else:
        r = context+'可对照研究问题、样本来源和评价指标，寻找现有临床积累能够切入的课题；先核对原文的局限性。'
    if 'business' in industry:
        b = context+'可观察资金或合作方投向什么场景，再对照自身产品寻找合作切口；交易进展仍以公告为准。'
    elif 'regulation' in industry:
        b = context+'可核对准入对象、预期用途和适用地区，帮助判断产品验证与申报路线；不宜把单项获批外推到同类产品。'
    elif 'products' in industry:
        b = context+'可对照新方案解决的用户问题与使用流程，判断你的现有产品适合补什么 AI 能力；商业披露需结合实际验证。'
    else:
        b = context+'可跟踪技术如何进入实际服务，比较数据条件、集成成本和验证需求，为产品升级排优先级。'
    return {'research': r, 'industry': b}

def update_history(path, items, profile, as_of):
    previous = [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()] if path.exists() else []
    merged = {row['item_id']: row for row in previous+items}
    if profile.get('editorial', {}).get('enabled'):
        for old in previous:
            if merged[old['item_id']].get('reading_tier') == 'archive' and old.get('reading_tier') != 'archive':
                merged[old['item_id']] = old  # Keep previously archived reading material, outside current selections.
    history_profile = {**profile, 'freshness_days': 20}
    # Preserve past membership; a historical record is not a newly model-scored recommendation.
    rows = [dict(row, freshness_gate=freshness_gate(row, as_of, 20)) if profile.get('editorial', {}).get('enabled')
            else score_item(row, history_profile, as_of) for row in merged.values()]
    rows = [r for r in rows if r['freshness_gate']=='fresh' and r.get('reading_tier', 'archive')!='archive']
    # A stable original URL wins over duplicate collector identities.
    unique = {r['url']: r for r in rows}
    rows = sorted(unique.values(), key=lambda r:(r['published_at'],r['item_id']), reverse=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
    return rows
