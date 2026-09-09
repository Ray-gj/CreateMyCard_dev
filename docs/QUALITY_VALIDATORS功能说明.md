# QUALITY_VALIDATORS 功能说明

## 1. 文档定位与执行机制

本文依据 2026-09-09 当前工作区源码和配置，介绍标准 A2UI 质量校验器，供开发和排障使用，不代表线上部署状态。正式约束以 [云侧方案设计](云侧方案设计.md) 为准，本文不新增协议或规则。

入口为 `widget_service/cloud/services/card_validation/pipeline.py`。当前共注册 12 项，即 11 个扩展美学校验器加 1 个对比度校验器。

> 文档差异：《美学校验设计成果总结》仍有“11 个扩展校验器未进入生产执行列表”的历史描述，而当前源码已注册全部 12 项。本文记录源码事实，不代替已有文档的确认与同步，也不推断部署状态。

| 请求阶段 | 执行阶段 | 质量检查 |
|---|---|---|
| `hard` | `hard` | 不执行 |
| `semantic` | `hard → semantic` | 不执行 |
| `quality` 或 `all` | `hard → semantic → quality` | 执行，但可能被阶段短路跳过 |

开启 `stop_on_stage_error` 时，前序错误可以阻止进入质量阶段。具体规则还会根据尺寸、组件类型、场景和字段可解析性跳过。校验器生成诊断，不自动修改卡片，也不直接适用于尚未转换的 Compact DSL。

扩展规则默认报 `error`，只有 `ICON.DUPLICATE_SRC` 和 `DENSITY.SINGLE_PRIMARY_ACTION` 报 `warning`；对比度自行决定级别。前 11 项共使用 23 个独立诊断码，对比度另使用 `VISUAL.CONTRAST`。

**诊断错误不等于交付失败。** 正式方案规定产物校验默认开启、失败重试默认关闭；开启重试后最多重新生成一次，仍失败时记录日志并保存最后一次输出。当前产物校验失败属于非阻断质量观测，不直接把生成响应改为 `failed`。

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

### 2.2 GradientValidator：渐变结构

目的：避免渐变缺少方向、色标不完整或位置乱序。

- 检查 `linearGradient` 和 `radialGradient`，渐变必须是对象。
- 线性渐变必须有非空字符串 `direction`，或 `0～360` 的数值 `angle`。
- 径向渐变必须有非空 `center`。
- 至少两个色标，每个包含合法静态颜色和 `0～1` 的数值位置。
- 位置必须严格递增，首个为 `0`，最后为 `1`。

诊断码：`GRADIENT.UNREGISTERED`。

边界：当前检查结构，不匹配渐变预设库；非空方向和中心不等于完整枚举或几何验证。识别属性不代表协议层允许属性。Alpha 档位由颜色校验补充检查。

### 2.3 AssetQualityValidator：图片来源

目的：控制不受信任的远程素材与内嵌图片。

检查 `Image.src` 和 `styles.backgroundImage`，拒绝识别到的 `data:image...`、`data:;base64...`。HTTP/HTTPS 图片按解析出的主机名核对允许名单；未配置允许主机时会触发诊断。

诊断码：`ASSET.REMOTE_SRC`。

边界：动态表达式跳过。本地路径通过不代表文件存在或已授权。不检查分辨率、清晰度、内容和风格，也不是完整 URI 安全检查器。

### 2.4 IconValidator：重复图标

目的：提醒同一区域存在重复图片，降低视觉冗余。

收集静态 `Image.src`，按“原始路径 + 父容器集合”分组。具有父容器且同组出现多次时，报告 `ICON.DUPLICATE_SRC` 警告。例如同一行的两个图片组件引用相同路径，会收到提示。

边界：不是全卡禁止重复，不同父容器中的相同图片不一定命中；动态图片不参与，也不识别装饰图标和业务图片。

### 2.5 ShapeValidator：圆角体系

目的：保持根卡片外形与按钮风格一致。

| 诊断码 | 当前规则 |
|---|---|
| `SHAPE.CARD_ROOT_RADIUS` | 根组件圆角为 `18～20vp`，包含边界 |
| `SHAPE.BUTTON_RADIUS` | 按钮已声明的数值圆角不小于 `18vp` |
| `SHAPE.RADIUS_FAMILY` | 多个按钮已声明的数值圆角保持一致 |

例如两个按钮分别使用 `18vp` 和 `20vp`，都满足最小值，但仍触发一致性问题。

边界：根圆角缺失会报错；按钮未声明圆角，不会由当前最小圆角检查主动补报。一致性仅针对 `Button`，不是所有可点击组件。

### 2.6 TypographyValidator：字体规范

目的：限制随意字号、字重及错误的自适应范围。

- 针对 `Text` 和 `Button`，检查 `fontSize`、`minFontSize`、`maxFontSize`。
- 当前字号档位：`10、12、14、16、18、20、32、40`。
- 最小和最大字号必须成对声明，且最小值不大于最大值。
- 数值字重必须属于 `100、200、300、400、500、600、700、800、900`。

诊断码：`TYPE.FONT_SIZE_STEP`、`TYPE.WEIGHT_MATRIX`。

边界：这是档位检查，不测量排版。例如 `24vp` 未必不可读，但不在当前允许档位。字段类型和协议合法性仍需前序校验负责。

### 2.7 CopyValidator：文案长度

目的：避免标题和操作文案挤占空间。

| 类型 | 2×2 | 2×4 | 诊断码 |
|---|---:|---:|---|
| 标题 | 最多 8 字符 | 最多 8 字符 | `COPY.TITLE_MAX_CHARS` |
| 操作 | 最多 6 字符 | 最多 8 字符 | `COPY.ACTION_LABEL_MAX_CHARS` |

`Button.label` 和有非空点击处理列表的 `Text.content` 作为操作文案。ID 包含 `title`、`header`、`kicker` 的 `Text` 作为标题，忽略大小写；同时满足两类时按操作处理。

支持解析部分首帧表达式、路径绑定和数值，检查展示文本，不以表达式源码长度代替显示长度。

边界：无法解析的动态文本跳过。按字符而非像素宽度判断，不能保证不换行、不截断，普通正文不受该项限制。

### 2.8 SpacingValidator：安全边距与间距档位

目的：防止内容贴边和间距不统一。

| 诊断码 | 当前规则 |
|---|---|
| `SPACING.SAFE_MARGIN` | 内容根四边 padding 必须均为 `12vp` |
| `SPACING.SCALE` | 间距属于 `0、2、4、6、8、10、12、14、16` |

检查 `styles.padding`、`styles.margin`，以及 `List.space` 或其他组件的 `itemMargin`。

对通过结构识别的融球卡片，安全边距检查实际内容根，不强制背景壳增加 padding，以保留满铺背景。

边界：`12vp` 是精确值，不是最小值。融球识别会检查结构，不是只看名字就豁免。不测量真实渲染内容与边缘的距离。

### 2.9 SlotValidator：区域组织

目的：检查内容区域、操作顺序与标题层级。

识别内容根，穿透部分仅有单个容器子项且当前层无直接操作的包装层，再检查：

| 诊断码 | 触发条件 |
|---|---|
| `SLOT.MODEL_REQUIRED` | 内容区域没有可解析子组件 |
| `SLOT.ORDER` | 最后一个含操作区域不在末尾 |
| `AREA.TITLE_TEXT_TIER` | 首个区域内识别到的标题数值字号不合尺寸档位 |

标题字号：2×2 为 `12vp`，2×4 为 `12vp` 或 `18vp`。标题识别依赖 ID 中的 `title`、`header`、`kicker`。

边界：不强制标题、正文、操作三个区域全部存在；找不到标题时跳过字号检查。顺序规则只检查最后一个操作区域的位置，不禁止其他区域包含操作。

### 2.10 DensityValidator：信息密度

目的：限制操作和突出数字，避免焦点分散。只针对 2×2、2×4，统计从根可达的组件。

| 检查项 | 2×2 上限 | 2×4 上限 | 诊断码 |
|---|---:|---:|---|
| 带非空点击处理列表的组件 | 1 | 2 | `DENSITY.EXPLICIT_ACTIONS` |
| 大字号数字文本 | 1 | 2 | `DENSITY.NUMBERS` |

大数字要求：组件为 `Text`、数值 `fontSize ≥ 24`、可解析文本去除首尾空白后以数字或带正负号的数字开头。

操作组件大于 1 时另报 `DENSITY.SINGLE_PRIMARY_ACTION` 警告。因此 2×4 两个操作不超过上限，但仍有突出单一主要操作的建议。

边界：统计点击组件，不对业务动作去重；父子均声明点击时可能分别计数。可达不等于渲染后可见，也不衡量文字面积或真实视觉密度。

### 2.11 Layout2x4Validator：2×4 布局尺寸

目的：发现已声明尺寸造成的溢出及等分不一致。只针对 2×4，从 `320×160vp` 初始参考空间出发，递归检查 `Row`、`Column`。

- 主轴：核算子项尺寸、margin、项目间距和容器 padding 总占用。
- 交叉轴：检查子项尺寸与对应 margin 是否超过可用空间。
- 等分：容器 ID 包含 `equal`、`grid`、`metrics`、`cells` 时，按扣除 padding 和间距后的空间核对等分。
- 尺寸比较允许 `1vp` 误差。

诊断码：`LAYOUT2X4.CLOSURE`、`LAYOUT2X4.EQUAL_SPLIT`。

边界：子项尺寸未全部确定时跳过等分检查。不完整模拟弹性布局、动态文字和未知尺寸；占用检查主要发现超出，不要求普通容器恰好填满。

### 2.12 ContrastValidator：文字对比度

目的：识别文字与有效背景太接近的问题。沿组件树继承背景，合成背景和文字 Alpha 后计算亮度对比度，主要检查有内容的 `Text`。统一诊断码为 `VISUAL.CONTRAST`。

| 纯色背景对比度 | 结果 |
|---|---|
| 小于 `3:1` | `error` |
| 大于等于 `3:1` 且小于 `4.5:1` | `warning` |
| 大于等于 `4.5:1` | 不报告问题 |

渐变采样色标及相邻颜色中点。至少三个对比度样本时取第二低值，容忍一个孤立最差样本；报告值低于 `4.5:1` 时仅发警告，要求渲染复核。

- 融球：背景来自兄弟装饰层合成，输出渲染复核警告，不作静态低对比度错误判定。
- 模板：遇到 `template_root` 时跳过该子树对比度检查，其他校验器不因此全部豁免。
- 无可解析背景时从白色参考背景开始合成；前景无法计算时可能不产生诊断。

边界：不真实渲染图片、不测量文字矩形，也不完整模拟装饰合成；渐变采样不等于按实际文字位置计算。融球识别口径不同于间距检查的完整结构识别。没有诊断不代表端侧一定可读。

## 3. 易混淆职责

| 对照 | 区别 |
|---|---|
| Color / Contrast | 颜色写法和透明度 / 文字可读性 |
| Gradient / Contrast | 渐变结构 / 渐变背景下的对比度 |
| Typography / Slot | 通用字体档位 / 标题区域字号 |
| Copy / Density | 单条文案长度 / 操作和大数字数量 |
| Spacing / Layout2x4 | 间距规范 / 尺寸是否装得下 |
| AssetQuality / Icon | 来源是否允许 / 同区域是否重复 |

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
| AssetQuality | `asset_quality_validator.py` |
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
