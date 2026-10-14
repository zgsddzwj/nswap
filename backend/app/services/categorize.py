"""发布分类自动识别（docs/11）：标题/描述关键词 → 类目。

发布端免选分类后，浏览端筛选的数据质量由本模块保证；
规则可维护（词表即配置），未命中归 other。
"""

CATEGORIES = {"baby", "book", "appliance", "furniture", "clothing", "digital", "sports", "kitchen", "other"}

_KEYWORDS: dict[str, list[str]] = {
    "baby": ["推车", "婴儿", "宝宝", "娃娃", "奶瓶", "尿不湿", "童床", "摇篮", "安抚", "儿童座椅", "学步"],
    "book": ["绘本", "教材", "小说", "漫画", "辅导", "习题", "杂志", "词典", "字典", "书"],
    "appliance": ["冰箱", "洗衣机", "空调", "电视", "净化器", "微波炉", "电饭煲", "吸尘器", "热水器", "风扇", "加湿器"],
    "furniture": ["沙发", "床垫", "书架", "鞋架", "茶几", "餐桌", "衣柜", "床", "桌子", "椅子", "柜"],
    "clothing": ["衣服", "外套", "上衣", "裤子", "裙子", "童装", "卫衣", "羽绒服", "鞋子", "球鞋", "凉鞋", "帽子"],
    "digital": ["手机", "电脑", "笔记本", "平板", "耳机", "相机", "键盘", "鼠标", "iphone", "ipad", "switch",
                "充电", "音箱", "手表", "无人机", "显示器"],
    "sports": ["篮球", "足球", "羽毛球", "乒乓球", "网球", "健身", "跑鞋", "自行车", "滑板", "滑轮", "哑铃",
               "瑜伽", "帐篷", "钓", "泳"],
    "kitchen": ["锅", "碗", "筷子", "勺子", "杯子", "水壶", "榨汁", "空气炸锅", "刀具", "砧板", "餐具", "烤箱"],
}


def guess_category(title: str, description: str = "") -> str:
    """按关键词命中打分：标题权重 2、描述权重 1、长词（书架>书）优先。

    未命中归 other。规则表即配置，覆盖冲突时优先加长词。
    """
    title_l = (title or "").lower()
    desc_l = (description or "").lower()
    best, best_score = "other", 0
    for category, words in _KEYWORDS.items():
        score = sum(
            len(w) * (2 if w in title_l else 0) + len(w) * (1 if w in desc_l else 0)
            for w in words
            if w in title_l or w in desc_l
        )
        if score > best_score:
            best, best_score = category, score
    return best
