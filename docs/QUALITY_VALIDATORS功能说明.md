# QUALITY_VALIDATORS 功能说明

## 1. 文档定位与执行机制

本文依据 2026-09-11 当前工作区源码和配置，介绍标准 A2UI 质量校验器，供开发和排障使用，不代表线上部署状态。正式约束以 [云侧方案设计](云侧方案设计.md) 为准，本文不新增协议或规则。

入口为 `widget_service/cloud/services/card_validation/pipeline.py`。当前完整质量管线注册 13 项：10 个扩展美学校验器，加融球专项、Stack 文字分区和通用对比度校验器。

> 2026-09-11：移除 AssetQualityValidator；SlotValidator（已移除） 取消 SLOT.ORDER，保留内容区域存在性与标题字号检查。基础 AssetValidator 不受此次调整影响。

| 请求阶段 | 执行阶段 | 质量检查 |
|---|---|---|
| `hard` | `hard` | 不执行 |
| `semantic` | `hard → semantic` | 不执行 |
| `quality` 或 `all` | `hard → semantic → quality` | 执行，但可能被阶段短路跳过 |

开启 `stop_on_stage_error` 时，前序错误可以阻止进入质量阶段。具体规则还会根据尺寸、组件类型、场景和字段可解析性跳过。校验器生成诊断，不自动修改卡片，也不直接适用于尚未转换的 Compact DSL。

扩展规则默认报 `error`，只有 `ICON.DUPLICATE_SRC` 报 `warning`；对比度自行决定级别。扩展规则的诊断以各节说明为准，对比度使用 `VISUAL.CONTRAST`。

**诊断错误不等于交付失败。** 正式方案规定产物校验默认开启、失败重试默认关闭；开启重试后最多重新生成一次，仍失败时记录日志并保存最后一次输出。当前产物校验失败属于非阻断质量观测，不直接把生成响应改为 `failed`。

### 1.1 字段路径约定与公共读取语义

本文的 `styles.xxx`、`onClick`、`children` 等路径均相对单个组件；不是要求新增字段。以下片段和数值示例仅解释规则，不代表完整可交付卡片。

| 上下文字段 | 含义及消费者 |
|---|---|
| `context.components` | 解析后的组件列表；Color、Gradient、Icon、Shape、Typography、Copy、Spacing 扫描全集 |
| `context.components_by_id` | ID 到组件的索引，用于引用解析与树遍历，不是要求在原始 DSL 新增同名结构 |
| `context.root_id` | 解析出的根 ID；Shape 确定根，Spacing 选择安全根，Density、Contrast 从根分析 |
| `context.cardspec.suggestSize` | 正式尺寸来源；Copy、Density 直接读取，不维护重复 card_size 字段 |
| `context.data_model` | 已解析的首帧数据；Copy 和 Density 用来获取可展示文本 |
| `rules.layout / style / asset` | RuleRegistry 加载相应 JSON 后提供的配置对象 |

**公共函数不是完整协议校验：**

- `numeric()` 接受非布尔整数、浮点数，以及可匹配的数字字符串；字符串允许 vp、fp、px 后缀，解析后只取数值，不做物理单位换算。不能解析返回 None。读取配置列表时，不少校验器另用严格数值类型过滤，不等同于 numeric()。
- `resolve_dimension()` 额外把字符串 matchParent 解析为父参考尺寸；百分比、动态表达式等不能由此解析。
- `spacing_tuple()` 按上、右、下、左返回四个方向；数值复制四份，字典缺失或不可解析的方向按 0，其他无法识别的值也按四个 0。该估算不等于字段合法。
- `display_text()` 处理普通字符串、支持静态求值的 `{{...}}` 字符串、含字符串 path 的绑定对象，以及非布尔数字；输出字符串或 None。路径/表达式结果为布尔、列表或字典时不作为可显示标量。
- `children_of()` 只返回 children 列表中可在索引找到的字符串 ID 对应组件。未知引用应由结构校验发现，不能将这里跳过理解为允许悬空引用。

**诊断路径说明：** `/updateComponents/components/{index}/...` 使用列表下标；`/updateComponents/componentsById/{id}/...` 是便于定位的 ID 视图，不表示原始 JSON 一定包含 componentsById。多组件汇总问题可能只定位组件集合。

## 2. 各校验器详细说明

### 2.1 ColorValidator：颜色格式与透明度

目的：统一颜色表示和透明度，避免整个组件透明化影响文字与内容。

扫描 `fontColor`、`textColor`、`fillColor`、`backgroundColor`、`borderColor`、`color` 及渐变色标颜色。

| 诊断码 | 规则 |
|---|---|
| `COLOR.INVALID_FORMAT` | 静态颜色必须为 `#AARRGGBB` |
| `COLOR.ALPHA_STEP` | Alpha 必须属于登记档位 |
| `COLOR.OPACITY_MISUSE` | 检测数值处于 `0 ≤ opacity < 1` 的组件透明度 |

示例：`#FFFFFF` 不合规，`#FFFFFFFF` 格式正确；`#80FFFFFF` 的 Alpha 为 128，当前允许。`opacity: 0.5` 会触发诊断，应按设计意图将透明度编码到具体颜色中。

边界：以 `{{`、`${`、`$theme(` 开头的动态颜色跳过静态格式判断。不判断配色协调性，不计算对比度，也不是全部非法透明度值的完整检查。

#### 字段与代码判定

| 字段路径 | 读取和判断 |
|---|---|
| `styles` | 必须是字典才扫描颜色 |
| `styles.fontColor / textColor / fillColor / backgroundColor / borderColor / color` | 只扫描存在的键；静态值去空白后匹配八位颜色，键存在但为 `null` 也会报格式错误 |
| `styles.linearGradient.colors[j][0]`、`styles.radialGradient.colors[j][0]` | 读取非空列表或元组色标的第一个元素 |
| `styles.opacity` | 经 `numeric()` 解析；不可解析或不在 `0 ≤ 值 < 1` 时不命中本规则 |
| `rules.style.allowedAlphaSteps` | 保留列表中 0～255 的非布尔整数；有效集合为空时回退 `ALPHA_STEPS` |

当前 Alpha 档位为 `0、12、13、25、26、38、39、51、77、102、127、128、153、178、179、204、229、230、255`。例如 `backgroundColor: "#11FFFFFF"` 格式合法，但 Alpha 为 17，会报档位错误。格式错误时不再继续判断该颜色的 Alpha。

诊断定位到 `/updateComponents/components/{index}/styles/{字段}`；渐变颜色继续定位到 `colors/{j}/0`。

源码：`widget_service/cloud/services/card_validation/quality/color_validator.py`。

### 2.2 GradientValidator：渐变结构

目的：避免渐变缺少方向、色标不完整或位置乱序。

- 检查 `linearGradient` 和 `radialGradient`，渐变必须是对象。
- 线性渐变必须有非空字符串 `direction`，或 `0～360` 的数值 `angle`。
- 径向渐变必须有非空 `center`。
- 至少两个色标，每个包含合法静态颜色和 `0～1` 的数值位置。
- 位置必须严格递增，首个为 `0`，最后为 `1`。

诊断码：`GRADIENT.UNREGISTERED`。

边界：当前检查结构，不匹配渐变预设库；非空方向和中心不等于完整枚举或几何验证。识别属性不代表协议层允许属性。Alpha 档位由颜色校验补充检查。

#### 字段与代码判定

| 字段路径 | 读取和判断 |
|---|---|
| `styles.linearGradient / radialGradient` | 缺失或 `null` 跳过；非字典报错后跳过该渐变后续检查 |
| `linearGradient.angle` | 必须为非布尔数值，范围 0～360，含端点；渐变背景使用 angle + colors 格式 |

| `radialGradient.center` | 仅检查真值，不验证内部坐标字段 |
| `gradient.colors` | 必须是至少两个元素的列表 |
| `gradient.colors[j][0]` | `static_color()` 要求静态八位颜色；动态颜色不满足 |
| `gradient.colors[j][1]` | 非布尔数值，范围 0～1，且大于前一个有效位置 |
| `rules` | 当前不消费配置 |

例如 `colors = [["#FFFFFFFF", 0], ["#FF000000", 1]]` 满足色标要求。两个位置都是 0.5 时，可能同时命中顺序与区间覆盖问题。同个渐变可有多条同码诊断，位置分别是渐变对象、colors 或具体色标。色标多余元素不由此处检查。

源码：`widget_service/cloud/services/card_validation/quality/gradient_validator.py`。

### 2.3 AssetQualityValidator：已移除

`AssetQualityValidator` 已从当前质量校验管线和源码中移除，本节历史说明不再代表当前生效规则。

### 2.4 IconValidator：重复图标

目的：提醒同一区域存在重复图片，降低视觉冗余。

收集静态 `Image.src`，按“原始路径 + 父容器集合”分组。具有父容器且同组出现多次时，报告 `ICON.DUPLICATE_SRC` 警告。例如同一行的两个图片组件引用相同路径，会收到提示。

边界：不是全卡禁止重复，不同父容器中的相同图片不一定命中；动态图片不参与，也不识别装饰图标和业务图片。

#### 字段与代码判定

| 字段路径 | 用途 |
|---|---|
| `context.components` | 扫描组件全集，而非仅根可达树 |
| `component / src` | Image、非空字符串，且去空白后不以 `{{` 或 `${` 开头 |
| 图片 `id` | 查找图片的父容器集合 |
| 父组件 `id / children` | `parents_by_id()` 据此构造引用关系 |
| `rules` | 不消费配置 |

分组键为 `(src, tuple(sorted(parent_ids)))`，没有父容器的图片不参加分组。每个重复组通常只报告一条警告，定位首个匹配项的 src。

例如两个图片的父集合都是 `{row_a}` 且原始 src 相同，会被分为一组；父集合分别为 `{row_a}` 和 `{row_b}` 则不同。分组用原始 src，不做路径归一化，也不以背景图字段参与统计。

源码：`widget_service/cloud/services/card_validation/quality/icon_validator.py`。

### 2.5 ShapeValidator：圆角体系

目的：保持根卡片外形与按钮风格一致。

| 诊断码 | 当前规则 |
|---|---|
| `SHAPE.CARD_ROOT_RADIUS` | 根组件圆角必须为 `20vp`，不允许中间值 |
| `SHAPE.BUTTON_RADIUS` | 按钮已声明的数值圆角必须为 `16vp` |
| `SHAPE.ICON_RADIUS` | 图标已声明的数值圆角必须为 `4vp` |`r`n| `SHAPE.RADIUS_FAMILY` | 多个按钮已声明的数值圆角保持一致 |

例如两个按钮分别使用 `18vp` 和 `20vp`，都满足最小值，但仍触发一致性问题。

边界：根圆角缺失或不是 20vp 会报错；按钮和图标未声明圆角时，不会主动补报。一致性仅针对 `Button`，不是所有可点击组件。

#### 字段与代码判定

| 字段路径 | 读取和判断 |
|---|---|
| `context.root_id` 与组件 `id` | 相等即视为根，不按固定名称猜测 |
| `styles.borderRadius` | 用 numeric() 解析；根要求精确命中允许档位 |
| `component = Button` | 检查最小圆角，并将已解析圆角放入去重集合 |
| `rules.layout.rootBorderRadius` | 单值表示固定圆角，列表表示离散允许值；元素须可解析且非负，按原顺序去重 |
| `rules.layout.minButtonRadius` | 可解析且非负时覆盖默认 18 |

非法根圆角配置回退固定默认值 `(20.0,)`。根没有字典 styles，或圆角缺失、不可解析、越界，都会报错。非根圆角不可解析时跳过按钮圆角统计。

例如配置为 `[20]` 时只允许 20；其它数值均不合法。按钮圆角集合为 `{18,20}` 时，圆角体系错误定位在组件集合，actual 为排序后的圆角值。

源码：`widget_service/cloud/services/card_validation/quality/shape_validator.py`。

### 2.6 TypographyValidator：字体规范

目的：限制随意字号、字重及错误的自适应范围。

- 针对 `Text` 和 `Button`，检查 `fontSize`、`minFontSize`、`maxFontSize`。
- 当前字号档位：`10、12、14、16、18、20、32、40`。
- 最小和最大字号必须成对声明，且最小值不大于最大值。
- 数值字重必须属于 `100、200、300、400、500、600、700、800、900`。

诊断码：`TYPE.FONT_SIZE_STEP`、`TYPE.WEIGHT_MATRIX`。

边界：这是档位检查，不测量排版。例如 `24vp` 未必不可读，但不在当前允许档位。字段类型和协议合法性仍需前序校验负责。

#### 字段与代码判定

| 字段路径 | 读取和判断 |
|---|---|
| `component / styles` | 仅 Text、Button 且 styles 为字典时执行 |
| `styles.fontSize / minFontSize / maxFontSize` | numeric() 可解析时核对字号档位 |
| `styles.minFontSize / maxFontSize` 的键存在性 | 通过键存在判断配对，不是通过值是否非空 |
| `styles.fontWeight` | numeric() 可解析时核对字重 |
| `rules.layout.allowedFontSizes / allowedFontWeights` | 列表中保留非布尔整数和浮点数，有效集合非空才覆盖默认 |

例如仅有 `minFontSize: 12` 报配对错误；`minFontSize:18, maxFontSize:12` 报顺序错误。两个键都存在但不能解析时，此处不会完成字段类型检查，仍需前序校验。

档位错误定位具体字段，配对或顺序错误定位 styles，actual 同时包含 minFontSize 和 maxFontSize。

源码：`widget_service/cloud/services/card_validation/quality/typography_validator.py`。

### 2.7 CopyValidator：文案长度

目的：避免标题和操作文案挤占空间。

| 类型 | 2×2 | 2×4 | 诊断码 |
|---|---:|---:|---|
| 标题 | 最多 9 字符 | 最多 22 字符 | `COPY.TITLE_MAX_CHARS` |
| 操作 | 最多 6 字符 | 最多 6 字符 | `COPY.ACTION_LABEL_MAX_CHARS` |

`Button.label` 和有非空点击处理列表的 `Text.content` 作为操作文案。ID 包含 `title`、`header`、`kicker` 的 `Text` 作为标题，忽略大小写；同时满足两类时按操作处理。

支持解析部分首帧表达式、路径绑定和数值，检查展示文本，不以表达式源码长度代替显示长度。

边界：无法解析的动态文本跳过。按字符而非像素宽度判断，不能保证不换行、不截断，普通正文不受该项限制。

#### 字段与代码判定

| 字段路径 | 用途与回退 |
|---|---|
| `context.cardspec.suggestSize` | 正式尺寸；标题长度按尺寸为 2x2 9、2x4 22；按钮长度按尺寸均为 6 |
| `component / label` | Button 检查 label，不要求声明点击处理 |
| `id / onClick / content` | 识别标题、操作型 Text 并检查 content |
| `context.data_model` | 供 display_text() 解析首帧文本 |
| 文案对象的 `path` | 字符串路径通过 read_pointer() 取值，不在字典分支解析其他任意表达式字段 |
| `rules.layout.titleMaxChars` | 非布尔正整数才采用，否则默认 8 |
| `rules.layout.titleMaxChars[suggestSize]` 与 `rules.layout.maxActionLabelChars[suggestSize]` | 对应尺寸的非布尔正整数才采用，否则回退尺寸默认值 |

例如 2x2 标题路径绑定在首帧解析出 10 个字符会报错；不能解析为可用标量则跳过。直接字符串先去首尾空白，路径读出的字符串按返回长度计算。布尔、列表和字典不是计数标量。诊断定位 label 或 content，actual 是字符数，不是整段文案。

源码：`widget_service/cloud/services/card_validation/quality/copy_validator.py`。

### 2.8 SpacingValidator：安全边距与间距档位

目的：防止内容贴边和间距不统一。

| 诊断码 | 当前规则 |
|---|---|
| `SPACING.SAFE_MARGIN` | 内容根四边 padding 必须均为 `12vp` |
| `SPACING.SCALE` | 间距属于 `0、2、4、6、8、10、12、14、16` |

检查 `styles.padding`、`styles.margin`，以及 `List.space` 或其他组件的 `itemMargin`。

对满足当前包装结构条件的融球或模板前景，安全边距检查选中的前景根，不强制外层背景壳增加 padding；具体选择见本节字段说明。

边界：`12vp` 是精确值，不是最小值。当前 `_safe_root_id()` 检查包装根与前景条件，但融球分支不验证整套装饰子树，不同于 Slot 使用的严格场景识别。不测量真实渲染内容与边缘的距离。

#### 字段与代码判定

| 字段路径 | 用途 |
|---|---|
| `context.root_id / components_by_id` | `_safe_root_id()` 选择安全边距目标 |
| 根 `component / children` | 只对 Stack 包装根尝试选择前景；含 root_0 时保留外根 |
| 前景 `id / component / children` | 前景须为 Row、Column、Stack；模板另核对包装结构 |
| `styles.padding` | 安全根四边必须等于目标；其他组件也做档位检查 |
| `styles.margin` | 核对已提供值的间距档位 |
| 顶层 `space / itemMargin` | List 读 space，其他组件读 itemMargin，不是 styles 内字段 |
| `rules.layout.allowedSpacing` | 列表中非布尔数值形成集合，无有效值时回退默认 |
| `rules.layout.defaultPadding` | numeric() 可解析即采用，默认 12；此处不额外限制配置非负 |

当前安全根选择步骤：

1. 从 context.root_id 开始。根不是 Stack、children 不是列表或含 root_0 时不切换。
2. 从子项中排除 fusionBallBackground，要求恰好剩一个可解析的容器前景。
3. 原子项含 fusionBallBackground 时选择该前景；此分支不验证整套融球装饰子树。
4. 没有融球标记时，前景须为 ID 等于 template_root 的 Stack，仅有一个 ID 以 `__genui_render_component__` 开头的容器子项；满足后选择 template_root 本身，不再下钻。

例如 padding 为四边各 12 的对象时满足安全边距；仅写 `{"top":12}` 时，其他方向按 0 参与安全边距判断并报错。一般档位检查只遍历字典已有值，空字典会报档位错误。

间距值为 null 时一般档位检查跳过，但安全根 padding 缺失仍报错。没有字典 styles 的非安全根会直接跳过，其顶层间距也不会在该轮检查。

源码：`widget_service/cloud/services/card_validation/quality/spacing_validator.py`。

### 2.9 SlotValidator（已移除）：区域组织

目的：检查内容区域、操作顺序与标题层级。

识别内容根，穿透部分仅有单个容器子项且当前层无直接操作的包装层，再检查：

| 诊断码 | 触发条件 |
|---|---|
| `SLOT.MODEL_REQUIRED` | 内容区域没有可解析子组件 |
| `AREA.TITLE_TEXT_TIER` | 首个区域内识别到的标题数值字号不合尺寸档位 |

标题字号：2×2 为 `12vp`，2×4 为 `12vp` 或 `18vp`。标题识别依赖 ID 中的 `title`、`header`、`kicker`。

边界：不强制标题、正文、操作三个区域全部存在；找不到标题时跳过字号检查。不限制操作区域的位置，已取消 SLOT.ORDER。

#### 字段与代码判定

| 字段路径 | 读取和判断 |
|---|---|
| `context.root_id / components_by_id` | quality_scene() 选择初始内容根；根不可解析则跳过 |
| `children` | children_of() 仅解析列表中已登记的字符串 ID，未知引用不计作区域 |
| 包装容器 `component / onClick` | Row、Column、Stack、List 仅一个容器子项且自身无直接操作时继续穿透 |
| 首区域后代 `component / id` | 寻找首个符合标题 ID 关键词的 Text |
| 标题 `styles.fontSize` | 可解析时才核对标题字号 |
| `context.cardspec.suggestSize` | 2x4 默认集合为 {12,18}，其他默认 {12} |
| `rules.layout.titleFontSizes[suggestSize]` | 对应列表中的非布尔数值形成集合，无有效值回退 |

这里仍使用 quality_scene() 的严格融球识别：外层 Stack 恰好两个有序子项，首个 fusionBallBackground，第二个内容 ID 有登记前缀，并校验背景槽和装饰组件类型、引用结构。它与 Spacing 的 `_safe_root_id()` 不同。

操作可以位于任意区域。内容区域存在性错误定位 `componentsById/{区域根ID}/children`，标题错误定位标题字号。

`SlotValidator` 已从当前质量管线移除，相关说明仅保留历史记录。

### 2.10 DensityValidator：大字号数字密度

2026-09-10 取消显式操作数量上限和默认只保留一个主要操作的限制，多操作不再触发密度错误或警告。
不再读取 `maxExplicitActions`。仅统计从根节点可达且去重后的大字号数字文本。

| 检查项 | 2x2 默认上限 | 2x4 默认上限 | 诊断码 |
|---|---|---|---|
| 字号至少 24 且文本以数字或正负号加数字开头的 Text | 1 | 2 | `DENSITY.NUMBERS` |

上限读取 `rules.layout.maxLargeNumbers[suggestSize]`，仅接受非布尔非负整数。
通过首帧数据解析绑定文本；未声明有效尺寸时跳过。超限输出 error，actual 为数量。

源码：`widget_service/cloud/services/card_validation/quality/density_validator.py`。

### 2.11 Layout2x4Validator（已移除）：2×4 布局尺寸

目的：发现已声明尺寸造成的溢出及等分不一致。只针对 2×4，从 `320×160vp` 初始参考空间出发，递归检查 `Row`、`Column`。

- 主轴：核算子项尺寸、margin、项目间距和容器 padding 总占用。
- 交叉轴：检查子项尺寸与对应 margin 是否超过可用空间。
- 等分：容器 ID 包含 `equal`、`grid`、`metrics`、`cells` 时，按扣除 padding 和间距后的空间核对等分。
- 尺寸比较允许 `1vp` 误差。

诊断码：`LAYOUT2X4.CLOSURE`、`LAYOUT2X4.EQUAL_SPLIT（历史规则）`。

边界：子项尺寸未全部确定时跳过等分检查。不完整模拟弹性布局、动态文字和未知尺寸；占用检查主要发现超出，不要求普通容器恰好填满。

#### 字段与代码判定

| 字段路径 | 用途 |
|---|---|
| `context.cardspec.suggestSize` | 仅精确等于 2x4 时执行 |
| `root_id / components_by_id / children` | 从根递归并按 ID 防止重复遍历，根不可解析则跳过 |
| `styles.width / height` | resolve_dimension() 解析数值或 matchParent，不解析百分比 |
| `styles.padding` | 换算上、右、下、左，扣除后取得内部空间 |
| 子项 `styles.margin` | 加入子项主轴和交叉轴占用 |
| 容器顶层 `itemMargin` | 主轴间距，不可解析时按 0，不读取 List.space |
| `component = Row / Column` | Row 主轴用宽、Column 主轴用高；其他容器不直接做闭合检查 |
| `id`、`rules.layout.equalSplitIdTokens` | 转小写做关键词包含匹配；配置保留非空字符串，无有效词回退默认 |

主轴总占用为“起始 padding + 结束 padding + 各子项尺寸与 margin 之和 + itemMargin × (子项数−1)”，超过容器尺寸加 1 才报溢出。

等分目标为“(主轴内部空间 − 总间距) ÷ 子项数”，比较子项尺寸加主轴 margin，不只是比较宽高。

示例：Row 宽 320、左右 padding 各 12、间距 8、两个子项无 margin，则等分目标为 144。均宽 144 满足该项；均宽 148 时总占用 328，超出容器。

未知子项尺寸只将已知 margin 纳入最低占用，并取消等分判断；递归遇到当前容器未知宽高时使用父参考空间。这些估算不能解释为真实渲染结果。

`Layout2x4Validator` 已从当前质量管线移除，相关说明仅保留历史记录。

### 2.12 ContrastValidator：文字对比度

目的：识别文字与有效背景太接近的问题。沿组件树继承背景，合成背景和文字 Alpha 后计算亮度对比度，主要检查有内容的 `Text`。统一诊断码为 `VISUAL.CONTRAST`。

| 纯色背景对比度 | 结果 |
|---|---|
| 小于 `2:1` | `error` |
| 大于等于 `2:1` 且小于 `4.5:1` | `warning` |
| 大于等于 `4.5:1` | 不报告问题 |

渐变采样色标及相邻颜色中点。至少三个对比度样本时取第二低值，容忍一个孤立最差样本；报告值低于 `2:1` 时报告 error，要求增强文字与背景对比度；`2:1 ≤ 报告值 < 4.5:1` 时报告 warning，要求渲染复核；达到 `4.5:1` 不报告问题。渐变不再自动将严重低对比度降为警告。

- 融球：背景来自兄弟装饰层合成，输出渲染复核警告，不作静态低对比度错误判定。
- 模板：遇到 `template_root` 时跳过该子树对比度检查，其他校验器不因此全部豁免。
- 无可解析背景时从白色参考背景开始合成；前景无法计算时可能不产生诊断。

边界：不真实渲染图片、不测量文字矩形，也不完整模拟装饰合成；渐变采样不等于按实际文字位置计算。融球识别依赖根子项标记，与 Spacing 的安全根选择、Slot 的严格场景识别并非同一逻辑。没有诊断不代表端侧一定可读。


#### 字段与代码判定

| 字段路径 | 用途与注意事项 |
|---|---|
| `context.components / root_id / components_by_id` | 缺少组件、根 ID 或可解析根时跳过 |
| 根 `children` | 含 fusionBallBackground 且不含 root_0 时进入融球复核模式 |
| 组件 `id` | 精确等于 template_root 时返回，不遍历该子树 |
| `styles.backgroundColor` | 接受六位 RGB 或八位 ARGB；叠加祖先背景，不透明纯色清除继承的渐变标记 |
| `styles.linearGradient / radialGradient` | 用 linearGradient or radialGradient 选择一个，不同时合成两者 |
| `gradient.colors[j][0]` | 提供采样颜色，不按 offset、方向或中心计算实际文字位置 |
| `component / content` | 仅 Text；字符串去空白后非空、字典非空、其他值不为 None 时进入检查 |
| `styles.fontColor / textColor` | 只要 fontColor 键存在就优先使用，即使值非法也不回退 textColor |
| `children` | 沿引用继续遍历，有效背景和场景状态向后代传递 |
| `rules` | 不消费配置，3 和 4.5 的阈值固定在源码中 |

与 Copy 不同，这里不调用 display_text()，也不读取 context.data_model；非空路径绑定字典可进入对比度检查。不读取字号和字重来切换阈值，Button.label 不在该项文字检查内。

纯色或渐变诊断 actual 为保留两位小数的比值；融球诊断为 `{"scene":"fusionBall","requiresRenderReview":true}`。位置为 `/updateComponents/componentsById/{id}/styles/{fontColor或textColor}`。

六位颜色可参与这里的计算，不代表满足 Color 的八位格式规则。

源码：`widget_service/cloud/services/card_validation/contrast_validator.py`。

## 3. 易混淆职责

| 对照 | 区别 |
|---|---|
| Color / Contrast | 颜色写法和透明度 / 文字可读性 |
| Gradient / Contrast | 渐变结构 / 渐变背景下的对比度 |
| Typography / Slot | 通用字体档位 / 标题区域字号 |
| Copy / Density | 单条文案长度 / 操作和大数字数量 |
| Spacing / Layout2x4 | 间距规范 / 尺寸是否装得下 |
| Icon | 同区域是否重复 |

`AestheticBaselineValidator` 不属于本列表，它位于静态校验列表，负责 emoji 图标和极小字号等最小审美硬基线。

## 4. 配置、源码与测试索引

以下路径相对仓库根目录。

| 文件 | 用途 |
|---|---|
| `widget_service/cloud/services/card_validation/pipeline.py` | 注册、阶段选择和短路 |
| `widget_service/cloud/services/card_validation/quality/common.py` | 场景、组件树、首帧文本及诊断级别 |
| `widget_service/cloud/data/validator_rules/config/layout.json` | 圆角、字体、间距、文案、密度、等分参数 |
| `widget_service/cloud/data/validator_rules/config/style.json` | Alpha 档位及其他样式参数 |
| `widget_service/cloud/data/validator_rules/config/diagnostics.zh-CN.json` | 中文诊断资源 |

配置可能包含其他链路使用的字段，不代表每项均由本组消费。渐变结构、对比度阈值和大数字识别条件等部分逻辑仍固定在源码中。

前 11 个实现文件位于 `widget_service/cloud/services/card_validation/quality/`：

| 校验器 | 文件 |
|---|---|
| Color | `color_validator.py` |
| Gradient | `gradient_validator.py` |
| AssetQuality | 已移除，不再注册 |
| Icon | `icon_validator.py` |
| Shape | `shape_validator.py` |
| Typography | `typography_validator.py` |
| Copy | `copy_validator.py` |
| Spacing | `spacing_validator.py` |
| Slot | `slot_validator.py` |
| Density | `density_validator.py` |
| Layout2x4 | `layout_2x4_validator.py` |
| Contrast | `widget_service/cloud/services/card_validation/contrast_validator.py` |

测试入口：

- `widget_service/tests/test_quality_validators.py`：扩展规则定向测试。
- `widget_service/tests/test_contrast_validator.py`：对比度及特殊背景测试。
- `widget_service/tests/test_aesthetic_baseline_validator.py`：硬基线测试，非本列表测试。

这些是验证入口，不表示本次文档整理执行了测试，也不固定测试数量。

## 5. 使用与维护建议

1. 排障先看位置、实际值和期望值，区分确定违规、设计建议和渲染复核。
2. 修改阈值前先确认正式方案；方案变更先同步总方案，再同步配置、实现与测试。
3. 不依赖 ID 绕过检查，标题、等分及场景标记只是识别线索，不是视觉正确性的证明。
4. 动态文本、图片背景、渐变及融球保留端侧渲染复核。
5. 区分源码注册、入口执行、部署启用、诊断错误和交付失败。

**结论：** 本组校验提供可定位、可解释的静态设计规则检查，能发现明确违规和部分布局风险，但不能替代协议校验、真实渲染和最终视觉验收。
