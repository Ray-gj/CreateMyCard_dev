# GenUI 通用格式与渐变、融球背景方案说明

## 1. 文档目的

本文汇总当前项目中 GenUI 最终产物的通用格式，以及两类常见背景方案：

- 普通显式渐变背景；
- 融球背景。

本文主要用于快速阅读、结构识别和排查问题，不替代正式方案。发生冲突时，仍按以下优先级判断：

1. `docs/云侧方案设计.md`；
2. `AGENTS.md`；
3. 在线生成链路的协议、Prompt 与实现；
4. 模板生成链路；
5. 离线历史样例。

本文参考的典型文件为：

| 文件 | 代表场景 | 用途 |
|---|---|---|
| `widget_service/cloud/services/card_validation/output/N001.dsl.jsonl` ～ `N060.dsl.jsonl` | 通用三行 GenUI、普通渐变 | 观察通用产物外壳和组件注册方式 |
| `widget_service/cloud/services/card_validation/health_sport.jsonl` | 橙色显式渐变 | 观察普通渐变背景结构 |
| `widget_service/cloud/services/card_validation/meeting.jsonl` | 蓝青融球 | 观察日程类融球结构和点击事件 |
| `widget_service/cloud/services/card_validation/sleep.jsonl` | 紫色融球 | 观察睡眠类融球结构 |

> 注意：三个典型文件用于说明视觉与结构特征，其中部分字段与当前正式约束不完全一致，不能直接复制为新的生产产物。差异见第 9 节。

## 2. 一页速览

### 2.1 GenUI 的固定外壳

一个标准 GenUI 文件是恰好三行的紧凑 JSONL，每行都是一个完整 JSON 对象：

```text
第 1 行：createSurface
第 2 行：updateComponents
第 3 行：updateDataModel
```

核心固定项：

- 三行都使用 `version: "v0.9"`；
- 三行的 `surfaceId` 必须完全一致；
- `catalogId` 使用 `ohos.a2ui.extended.catalog.form`；
- `updateComponents.root` 指向组件注册表中的根组件 ID；
- `updateDataModel.path` 通常为 `/`；
- 动态数据放在 `updateDataModel.value.data` 下。

本次检查 `output/` 目录中的 60 份 `Nxxx.dsl.jsonl` 后，观察结果一致：它们都是三行、三行
`surfaceId` 一致，root ID 均为 `root`、root 类型均为 `Column`，并且 root 都带有显式
`linearGradient`。这组样本可以作为通用三行外壳的集中参考，但具体字段仍需服从当前正式方案。

### 2.2 两种背景的核心区别

| 对比项 | 普通渐变 | 融球 |
|---|---|---|
| 根组件 | 通常是内容根，如 `Column` | 必须由外层 `Stack` 承担叠放 |
| 背景位置 | 直接写在 root 的 `styles.linearGradient` | 独立的 `fusionBallBackground` 背景分支 |
| 内容位置 | root 的普通子树，典型入口为 `root_0` | 与背景并列的 `__genui_render_component__root` 分支 |
| 背景构成 | 2～3 个渐变色标 | 3 个圆形 `Divider` + 1 个玻璃层 |
| 是否存在 `FusionBall` 组件 | 否 | 否；融球只是确定性展开后的标准组件树 |
| 对比度处理 | 可静态分析渐变色标，但仍可能需要渲染复核 | 融球专项只拆分并检查受控结构，不做对比度或渲染复核 |

## 3. GenUI 通用三行格式

### 3.1 最小骨架

下面的代码块为了阅读进行了换行。写入 `.jsonl` 文件时，每个顶层对象必须各自压缩成一行，不能把一个对象拆成多行。

```json
{"version":"v0.9","createSurface":{"surfaceId":"surface_card","catalogId":"ohos.a2ui.extended.catalog.form"}}
{"version":"v0.9","updateComponents":{"surfaceId":"surface_card","root":"root","components":[{"id":"root","component":"Column","children":["title"],"styles":{"width":"matchParent","height":"matchParent","padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF"}},{"id":"title","component":"Text","content":"示例卡片","styles":{"fontSize":16,"fontWeight":700,"fontColor":"#FF000000","maxLines":1}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"surface_card","path":"/","value":{"data":{}}}}
```

### 3.2 三行职责

#### 第 1 行：`createSurface`

负责创建渲染 Surface：

```json
{
  "version": "v0.9",
  "createSurface": {
    "surfaceId": "surface_card",
    "catalogId": "ohos.a2ui.extended.catalog.form"
  }
}
```

约束：

- 这里只声明协议版本、Surface 标识和组件目录；
- 不在 `createSurface` 中声明卡片 `width`、`height`；
- 卡片外围尺寸由 root 的 `styles.width/height` 与尺寸 profile 共同确定。

#### 第 2 行：`updateComponents`

负责声明根组件和全部组件：

```json
{
  "version": "v0.9",
  "updateComponents": {
    "surfaceId": "surface_card",
    "root": "root",
    "components": [
      {
        "id": "root",
        "component": "Column",
        "children": ["title"]
      },
      {
        "id": "title",
        "component": "Text",
        "content": "示例卡片"
      }
    ]
  }
}
```

组件不是递归嵌套对象，而是一个扁平注册表：

```text
components[]
├── { id: "root", children: ["title"] }
└── { id: "title" }
```

树关系通过 `children` 中的组件 ID 建立。因此需要保证：

- 每个 `id` 唯一；
- `root` 指向的 ID 存在；
- 每个 `children` 引用都能解析到真实组件；
- 不形成环；
- 没有需要渲染但无法从 root 到达的孤立组件。

#### 第 3 行：`updateDataModel`

负责首帧动态数据：

```json
{
  "version": "v0.9",
  "updateDataModel": {
    "surfaceId": "surface_card",
    "path": "/",
    "value": {
      "data": {
        "healthSport": {
          "dailySteps": 6200
        }
      }
    }
  }
}
```

组件中的绑定路径必须能在这里找到对应首帧值，且值类型与数据定义一致。

### 3.3 动态绑定

典型的完整 Expression：

```json
{"content":"{{ ${/data/healthSport/dailySteps} }}"}
```

静态文案和动态值拼接：

```json
{"content":"{{ '消耗热量 ' + ${/data/healthSport/dailyTotalCaloriesText} }}"}
```

事件参数也可以绑定动态字段：

```json
{
  "onClick": [
    {
      "call": "clickToIntent",
      "args": {
        "intentName": "ViewCalendarEvent",
        "params": {
          "entityId": "{{ ${/data/calendar/events/0/entityId} }}"
        }
      }
    }
  ]
}
```

不要只写裸路径字符串，例如 `"/data/healthSport/dailySteps"`，因为它会被当作普通文本，而不是绑定表达式。

### 3.4 通用 root 外壳

按当前正式方案，最终 A2UI root 至少应满足：

```json
{
  "id": "root",
  "styles": {
    "width": "matchParent",
    "height": "matchParent",
    "borderRadius": 18,
    "clip": true
  }
}
```

说明：

- `2x2` 的参考画布是 `160vp × 160vp`，`2x4` 的参考画布是 `320vp × 160vp`；
- 参考尺寸用于内部布局预算，不等于 root 要写死数值；
- root 的 `width/height` 应写 `"matchParent"`；
- root 圆角的正式口径是 `18`，并开启裁剪；
- root 还需要提供合规背景：纯色、渐变、受控背景图，或转换器展开后的融球背景。

## 4. 普通显式渐变背景

### 4.1 典型结构

`health_sport.jsonl` 的结构可简化为：

```text
root: Column
└── root_0: Stack
    └── root_0_0: Column
        ├── 上半区：标题、图标、步数、进度
        └── 下半区：热量、距离
```

背景直接写在 root 上：

```json
{
  "id": "root",
  "component": "Column",
  "children": ["root_0"],
  "styles": {
    "width": 160,
    "height": 160,
    "padding": 12,
    "borderRadius": 18,
    "clip": true,
    "backgroundColor": "#FFED6F21",
    "justifyContent": "spaceBetween",
    "linearGradient": {
      "direction": "RightBottom",
      "colors": [
        ["#FFED6F21", 0],
        ["#FFF9A01E", 1]
      ]
    }
  }
}
```

这是典型文件的原始写法，其中固定 `160 × 160` 仅用于说明样例现状。新产物应将 root 的宽高改为 `"matchParent"`。

### 4.2 背景与内容的关系

普通渐变不额外生成背景组件，渲染逻辑可理解为：

```text
root 自身绘制 backgroundColor
       ↓
root 自身叠加 linearGradient
       ↓
root 的 children 在同一内容树中绘制
```

`backgroundColor` 可以作为渐变绘制前的稳定底色。若渐变色带透明度，还需要考虑它与底色合成后的真实颜色。

### 4.3 `health_sport.jsonl` 的内容绑定

| 展示内容 | 绑定路径或值 |
|---|---|
| 今日步数 | `/data/healthSport/dailySteps` |
| 步数进度 | `value` 绑定每日步数，`total` 为 `10000` |
| 消耗热量 | `/data/healthSport/dailyTotalCaloriesText` |
| 运动距离 | `/data/healthSport/dailyDistanceText` |

数据模型根为：

```text
/data/healthSport
```

### 4.4 普通渐变的识别标记

当前对比度校验逻辑会参考 root 的直接子组件 ID：

```text
root.children 中存在 root_0 → 按普通场景处理
```

`root_0` 是现有样例和校验器使用的结构标记，不是 A2UI 协议中的新组件类型。

### 4.5 适用特点

普通渐变适合：

- 大多数单业务和多业务卡片；
- 需要稳定、可预期背景的场景；
- 不能满足融球版本或语义门禁的场景；
- 需要更容易做静态可读性分析的场景。

## 5. 融球背景

### 5.1 融球不是新组件

融球不是名为 `FusionBall` 的 A2UI 组件。最终产物仍只使用标准组件：

- `Stack` 负责背景和前景叠放；
- 三个圆形 `Divider` 负责绘制大、中、小色球；
- 另一个 `Divider` 负责半透明玻璃层；
- 原内容树作为前景分支覆盖在背景之上。

如果输入中直接出现 `component: "FusionBall"`，仍应按不支持组件处理。

### 5.2 固定结构

`meeting.jsonl` 和 `sleep.jsonl` 使用相同的融球外壳：

```text
root: Stack（透明外壳）
├── fusionBallBackground: Stack（背景分支）
│   ├── fusionBallLargeSlot: Stack
│   │   └── fusionBallLarge: Divider
│   ├── fusionBallMediumSlot: Stack
│   │   └── fusionBallMedium: Divider
│   ├── fusionBallSmallSlot: Stack
│   │   └── fusionBallSmall: Divider
│   └── fusionBallGlassLayer: Divider
└── __genui_render_component__root: Column（前景内容分支）
```

这里最重要的是背景和前景是 root 下的兄弟分支，不是父子关系。

### 5.3 外层 root

典型样例中的外层结构为：

```json
{
  "id": "root",
  "component": "Stack",
  "children": [
    "fusionBallBackground",
    "__genui_render_component__root"
  ],
  "styles": {
    "width": 160,
    "height": 160,
    "padding": 0,
    "borderRadius": 18,
    "clip": true,
    "backgroundColor": "#00000000",
    "alignContent": "topStart"
  }
}
```

关键点：

- `component` 使用 `Stack`，用于实现背景在下、内容在上的叠放；
- `backgroundColor` 为全透明；
- `fusionBallBackground` 必须排在内容分支之前；
- 最终正式产物的 root 宽高应使用 `"matchParent"`；
- root 必须开启 `clip`，避免超出画布的大球泄漏到卡片外。

### 5.4 背景组件职责

| 组件 ID | 组件类型 | 职责 |
|---|---|---|
| `fusionBallBackground` | `Stack` | 容纳全部融球装饰并统一裁剪 |
| `fusionBallLargeSlot` | `Stack` | 确定大球的位置和可见区域 |
| `fusionBallLarge` | `Divider` | 绘制大圆球 |
| `fusionBallMediumSlot` | `Stack` | 确定中球的位置和可见区域 |
| `fusionBallMedium` | `Divider` | 绘制中圆球 |
| `fusionBallSmallSlot` | `Stack` | 确定小球的位置和可见区域 |
| `fusionBallSmall` | `Divider` | 绘制小圆球 |
| `fusionBallGlassLayer` | `Divider` | 绘制半透明玻璃覆盖层并执行背景模糊 |

圆球的本质是高宽相等、圆角为半径的 `Divider`，例如：

```json
{
  "id": "fusionBallMedium",
  "component": "Divider",
  "styles": {
    "width": 160,
    "height": 160,
    "strokeWidth": 0,
    "color": "#00000000",
    "borderRadius": 80,
    "backgroundColor": "#FF2BA2D9",
    "clip": true
  }
}
```

玻璃层的典型写法：

```json
{
  "id": "fusionBallGlassLayer",
  "component": "Divider",
  "styles": {
    "width": 160,
    "height": 160,
    "strokeWidth": 0,
    "color": "#00000000",
    "backgroundColor": "#0DFFFFFF",
    "backdropBlur": {
      "radius": 120
    }
  }
}
```

### 5.5 内容根重命名

融球展开前，模型或模板中的原内容根通常叫 `root`。展开后：

```text
原内容根：root
     ↓ 加前缀
前景内容根：__genui_render_component__root
     ↓ 新建外壳
最终公共根：root
```

这个重命名有两个目的：

- 给新的外层 `Stack` 腾出标准 root ID；
- 使用 `__genui_render_component__` 前缀保留渲染器需要的防溢出标识。

前景内容根上的背景样式会被移除，宽高调整为 `"matchParent"`，让背景统一由融球分支承担。

### 5.6 两个典型融球样例

| 对比项 | `meeting.jsonl` | `sleep.jsonl` |
|---|---|---|
| 主题 | 蓝青日程 | 紫色睡眠 |
| 组件数 | 19 | 21 |
| 大球颜色 | `#FF172F73` | `#FF551773` |
| 中球颜色 | `#FF2BA2D9` | `#FF572BD9` |
| 小球颜色 | `#FF00D9C3` | `#FF0024D9` |
| 主内容 | 倒计时天数、时间、日程标题 | 睡眠类型、总时长、睡眠进度、深睡时长 |
| 数据根 | `/data/countdown`、`/data/calendar` | `/data/healthSport` |
| 图标 | 无 | 月亮图标 |
| 点击事件 | 整个前景内容根可打开日历事件 | 无 |

`meeting.jsonl` 的事件绑定为：

```text
clickToIntent / ViewCalendarEvent
└── params.entityId → /data/calendar/events/0/entityId
```

## 6. A2UI 模型输出与确定性展开

### 6.1 模型不直接生成完整融球树

当前 Design Compact 模型只需要在符合条件的 root 上输出受控 Design Token，例如：

```json
["root","Column",{"design":"fusion-ball-schedule-cool"},["content"]]
```

完整融球背景由转换器确定性展开，链路为：

```text
用户需求与 TaskSpec
        ↓
Design Compact Prompt
        ↓
模型输出极简组件行和 root.design
        ↓
Compact DSL 严格解析、归一化与校验
        ↓
版本、尺寸、root 类型、Token 门禁
        ↓
标准 A2UI 组件转换
        ↓
确定性展开融球背景树
        ↓
三行 GenUI JSONL
```

这样可以避免模型自由生成球体尺寸、位置、玻璃层和特殊 ID，保证同一 Token 的输出结构稳定。

### 6.2 当前 Design Compact 融球 Token

| Design Token | 主要用途 | 当前实现的大/中/小球颜色 |
|---|---|---|
| `fusion-ball-schedule-cool` | 冷色日程、提醒 | `#FF121E59` / `#FF2BA2D9` / `#FF52CCCC` |
| `fusion-ball-schedule-warm` | 暖色日程、提醒 | `#FF731D28` / `#FFFF5533` / `#FFE68A2E` |
| `fusion-ball-sleep-violet` | 睡眠、专注单主题 | `#FF2B2459` / `#FF572BD9` / `#FFB398D9` |
| `fusion-ball-sport-orange` | 单个倒计时、纪念日 | `#FFB33C24` / `#FFFF8833` / `#FFFAA89E` |

这些是当前 `fusion_ball_expander.py` 的实现色板，不等于两个典型 JSONL 文件中的历史色值。

### 6.3 Design Compact Prompt 的使用范围

当前 Prompt 只允许在以下前提同时满足时选择融球：

- 卡片尺寸为 `2x2`；
- 单一业务、单一数据域；
- 单个倒计时或纪念日；或者
- 单个日程、提醒；或者
- 睡眠、专注单主题。

明确禁止的模型生成场景包括：

- 天气；
- 电量；
- 运动列表；
- 系统工具；
- 设备状态；
- 组合通勤；
- 多个日程；
- 多业务或多数据域卡片。

注意：上述业务语义主要由 Prompt 约束。转换器的硬门禁不会重新理解整个业务语义。

### 6.4 转换器硬门禁

转换器确定性检查：

- 请求版本是否启用融球；
- 卡片是否为 `2x2`；
- root 是否唯一；
- root 类型是否为 `Row`、`Column` 或 `Stack`；
- `design` 是否为已登记的融球 Token。

默认配置的最低版本为：

```text
11.7.5.206
```

以下情况均失效关闭：

- 请求版本缺失；
- 配置的最低版本缺失；
- 任一版本格式非法；
- 请求版本低于最低版本。

关闭时有两层保护：

1. Prompt 追加运行时限制，要求模型不要生成 `fusion-ball-*`；
2. 转换器再次检查，即使模型仍生成 Token，也不展开融球。

不能只依赖模型自行判断版本。

### 6.5 融球不可用时的降级

如果模型输出融球 Token，但硬门禁未通过，转换器会：

- 移除未生效的 `design`；
- 不生成 `fusionBallBackground`；
- 为无背景 root 补充确定性的普通浅色渐变。

当前兜底渐变从六套浅色方案中确定性选择，选择依据来自完整源 Compact DSL 的 SHA-256。因此同一份输入可以稳定得到同一套兜底背景，而不是每次随机变化。

### 6.6 模板链路不是同一套场景范围

模板链路也可以展开融球，但它和 Design Compact 模型链路的使用范围不同：

| 链路 | 当前融球主题范围 |
|---|---|
| Design Compact 模型链路 | 日程、提醒、睡眠、专注、单个倒计时或纪念日 |
| 模板链路 | 日程、睡眠、运动/倒计时、天气、电量/蓝牙设备等受控模板主题 |

因此：

- 不要把模板的融球适用主题直接复制到模型 Prompt；
- 不要反过来用模型 Prompt 的限制删除模板已经登记的受控主题；
- 修改任一链路前，先确认目标属于模型生成还是模板生成。

## 7. 对比度校验如何识别两种场景

### 7.1 场景判定

当前结构标记为：

```text
存在 fusionBallBackground，且不存在 root_0 → 融球场景
存在 root_0                            → 普通场景
两者同时存在                           → 优先按普通场景处理
```

优先普通场景是为了避免普通内容分支因为碰巧存在融球命名而被错误放宽。

### 7.2 普通渐变

普通渐变可以读取 `linearGradient` 的色标并进行静态分析。由于真实渲染还受位置、渐变方向、透明度和文字覆盖区域影响，低对比度结果可能要求端侧渲染复核。

当前对 `health_sport.jsonl` 的实测中，5 个文字组件进入渐变渲染复核 warning；静态比值包括 `1.75:1` 和 `2.52:1`。

### 7.3 融球

融球背景和文字内容位于兄弟分支：

```text
root（透明）
├── fusionBallBackground（真实背景）
└── __genui_render_component__root（文字内容）
```

如果只沿内容父链向上查找背景，最终会落到透明 root，再错误继承默认白底，导致白字对白底的伪造结果 `1.00:1`。

当前校验器识别到融球结构后，只检查转换器展开出的标准组件树：根、背景 Stack、三个球槽、三个球体和玻璃层的引用、类型、尺寸、对齐、裁剪、圆角、颜色及 blur 参数。它不合成球色与玻璃背景，不计算文字或图标对比度，也不生成端侧渲染复核诊断。

## 8. 三个典型文件的当前校验结果

使用当前 `validate_card(dsl_text=...)` 校验时：

| 文件 | Errors | Warnings | 主要原因 |
|---|---:|---:|---|
| `health_sport.jsonl` | 2 | 5 | 2 个 root 固定宽高错误；5 个显式渐变对比度复核 warning |
| `meeting.jsonl` | 按当前结构结果 | 0 个融球复核 | 融球只执行展开结构和固定几何检查 |
| `sleep.jsonl` | 按当前结构结果 | 0 个融球复核 | 融球只执行展开结构和固定几何检查 |

三份文件的两个共同错误都是：

```text
root.styles.width  = 160 → 当前要求 "matchParent"
root.styles.height = 160 → 当前要求 "matchParent"
```

因此应把它们看作“典型结构与视觉参考”，而不是“可直接通过当前全部校验的标准产物”。

## 9. 当前需要特别注意的口径差异

以下差异已经存在于方案、Prompt、转换器和典型样例之间。未经过方案确认前，不应自行选一个口径批量修改代码或样例。

### 9.1 渐变方向：`direction` 与 `angle`

| 来源 | 当前写法 |
|---|---|
| `health_sport.jsonl` 等最终典型 GenUI | `linearGradient.direction: "RightBottom"` |
| Design Compact Prompt 与转换器 | `linearGradient.angle: 180` |
| 未启用的 `GradientValidator` 口径 | 要求 `direction` 或 `center` |

当前生产质量校验主要使用的校验器组合没有因此拦截 `angle`，但这不代表两种格式已经正式统一。

### 9.2 root 圆角：`18` 与 `20`

| 来源 | 当前写法 |
|---|---:|
| `docs/云侧方案设计.md` | `18` |
| 普通输出目录与三个典型样例的外层 root | `18` |
| Design Compact Prompt | `20` |
| 当前 Design Compact 融球展开器 | `20` |
| 模板融球外壳 | `18` |

正式方案优先级最高，因此新方案设计应以 `18` 为目标；但涉及现有实现同步修改时，需要先确认影响范围并补齐测试。

### 9.3 root 尺寸：固定值与 `matchParent`

| 来源 | 当前写法 |
|---|---|
| 三个典型 JSONL | `160 × 160` |
| 当前正式方案和 validator | `"matchParent" × "matchParent"` |
| 当前 Design Compact 融球展开器 | 外层 root 与前景根使用 `"matchParent"` |

内部球体和 slot 可以按参考画布进行确定性计算；当前展开器会将相关尺寸转换为相对百分比，以适应外层实际 Surface。

### 9.4 融球调色板：典型样例与当前实现不同

| 主题 | 典型文件 | 当前实现 |
|---|---|---|
| 日程冷色 | `#FF172F73 / #FF2BA2D9 / #FF00D9C3` | `#FF121E59 / #FF2BA2D9 / #FF52CCCC` |
| 睡眠紫色 | `#FF551773 / #FF572BD9 / #FF0024D9` | `#FF2B2459 / #FF572BD9 / #FFB398D9` |

生成新产物时应跟随当前受控 Token 的实现色板；典型文件的颜色仅用于理解视觉方向。

### 9.5 业务语义主要由 Prompt 约束

转换器会验证版本、尺寸、root 类型和 Token，但不会重新判断“这是天气还是日程”“是否为多业务”等完整语义。

因此，如果已启用版本下的模型误把一个已登记 Token 用到不允许的业务，转换器仍可能展开融球。这是当前边界，不应把转换器门禁描述为完整业务规则引擎。

### 9.6 `backdropBlur` 的协议白名单风险

融球玻璃层使用：

```json
{"backdropBlur":{"radius":120}}
```

但标准 Form 样式清单未明确列出该字段，当前组件校验器也没有落实所有 style 字段的逐项白名单检查。因此“当前没有被拦截”不等于“协议层已经明确批准”。如需收紧样式白名单，应先确认玻璃层的正式协议表达。

## 10. 阅读和生成检查清单

### 10.1 阅读任意 GenUI 文件

按以下顺序检查，最快定位结构：

1. 是否恰好三行 JSONL；
2. 三行 `version` 和 `surfaceId` 是否一致；
3. `catalogId` 是否正确；
4. `updateComponents.root` 指向哪个组件；
5. root 是 `Column`、`Row` 还是 `Stack`；
6. root 的 `children` 中是否有 `root_0` 或 `fusionBallBackground`；
7. `components[]` 的 children 引用是否完整；
8. Text、Image、Progress 和事件使用了哪些数据路径；
9. `updateDataModel.value` 是否提供对应首帧值；
10. root 是否使用 `matchParent`、圆角 `18` 和 `clip: true`。

### 10.2 生成普通渐变

- 背景直接放在 root 的 `styles` 中；
- 保留稳定底色或确认渐变完全不透明；
- 使用同色系 2～3 个 stop；
- 保证文字在各个可能覆盖区域都可读；
- root 下使用正常内容分支；
- 不生成 `fusionBallBackground`；
- 最终产物通过端侧渲染复核渐变上的文字。

### 10.3 生成融球

- 模型只输出允许的 root `design` Token；
- 不让模型手写完整融球树；
- 不生成 `FusionBall` 组件；
- 同时满足 `2x2`、版本和业务场景限制；
- 最终 root 为透明 `Stack`；
- root children 按背景、前景顺序排列；
- 背景 ID 固定为 `fusionBallBackground`；
- 内容根使用 `__genui_render_component__root`；
- 三个球使用标准 `Divider`；
- 玻璃层位于三个球之后、内容层之前；
- 端侧对真实渲染结果做文字可读性复核。

### 10.4 不要直接照抄典型样例的字段

至少需要复核：

- root 固定 `160 × 160` 是否应改为 `matchParent`；
- root 圆角是否遵循正式方案的 `18`；
- 渐变方向到底使用最终 A2UI 的 `direction`，还是 Compact DSL 的 `angle`；
- 融球颜色是否来自当前 Token 色板；
- `backdropBlur` 是否已获得正式协议支持；
- 目标链路是 Design Compact 模型链路还是模板链路；
- 目标 App 版本是否达到配置门槛。

## 11. 相关实现与文档索引

| 内容 | 文件 |
|---|---|
| 云侧总方案与最终协议约束 | `docs/云侧方案设计.md` |
| 字段约束演进 | `widget_service/cloud/services/card_validation/字段约束与演进记录.md` |
| 对比度场景识别和实测 | `docs/对比度校验方案演进.md` |
| Design Compact 生成规则 | `widget_service/cloud/data/protocol_profiles/design-compact-dsl/PROMPT.md` |
| Prompt 运行时版本限制 | `widget_service/cloud/services/prompt_builder.py` |
| Compact DSL 到 A2UI 转换 | `widget_service/cloud/services/compact_dsl_a2ui_converter.py` |
| 融球版本门禁、色板和组件展开 | `widget_service/cloud/services/fusion_ball_expander.py` |
| 生成管线 | `widget_service/cloud/services/generation_pipeline.py` |
| 60 份通用格式样本 | `widget_service/cloud/services/card_validation/output/` |
| 普通渐变典型样例 | `widget_service/cloud/services/card_validation/health_sport.jsonl` |
| 日程融球典型样例 | `widget_service/cloud/services/card_validation/meeting.jsonl` |
| 睡眠融球典型样例 | `widget_service/cloud/services/card_validation/sleep.jsonl` |

## 12. 最终记忆点

可以用下面三句话快速记住全部结构：

1. GenUI 是 `createSurface → updateComponents → updateDataModel` 三行 JSONL。
2. 普通渐变把 `linearGradient` 直接放在 root；融球把 `fusionBallBackground` 和前景内容作为 root 下的兄弟分支。
3. 模型只选择受控融球 Token，完整融球树由转换器在版本、尺寸和 Token 门禁通过后确定性展开。
