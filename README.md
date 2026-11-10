# ellia-pages

静态页面集合。每个页面是一个独立目录，可以单独构建，也可以从仓库根目录全量构建到 `dist/`。

## 目录结构

```text
ellia-pages/
├─ build.py                    # 全站构建入口
├─ dist/                       # 构建输出，已 gitignore
├─ gamejam/
│  ├─ page.toml                # 页面清单
│  ├─ build.py                 # 可选的页面级构建钩子
│  ├─ .gitignore               # 页面本地忽略项
│  ├─ index.html               # 目录页
│  ├─ mirror-2610/
│  │  ├─ index.html            # mirror 主题主页
│  │  ├─ content-field.js      # canvas 背景与上升粒子场
│  │  └─ mirror-lab.html       # mirror.js 实验页（源码专用，不发布）
│  ├─ js/
│  │  └─ effects/
│  │     ├─ fade.js            # 逐元素淡入淡出序列
│  │     ├─ mirror.js          # 共享 mirror 效果模块
│  │     └─ parallax.js        # 可复用视差模块（封面/象限/排行榜）
│  ├─ libs/
│  │  └─ three/
│  │     ├─ three.bundle.js
│  │     ├─ three-bundle-loader.js
│  │     ├─ vendor/
│  │     │  ├─ three.core.js
│  │     │  ├─ three.module.js
│  │     │  └─ three.LICENSE
│  │     └─ src/
│  │        └─ three-bundle-entry.js   # esbuild 输入，不发布
│  └─ tools/                   # 测试/工具脚本，不进入 dist
└─ openspec/
```

`mirror-2610/index.html` 使用 `js/effects/mirror.js`、`js/effects/fade.js`、`js/effects/parallax.js` 和共享 three loader；启动时先加载 three，再预检 HTML-in-Canvas 并选择 WebGL / SVG 后端。`libs/three/` 由 mirror lab 和后续 WebGL 页面共享；`parallax.js` 挂载在封面文字、象限文本和排行榜图层上。

目录页 `gamejam/index.html` 是一个独立的 Material 3 风格首页，支持切换 seed color；只在“页面”区展示 `MIRROR / 2610`。`mirror-lab.html` 只保留在源码树里给探针脚本用，既不在目录页出现，也不会进入构建产物。

当前页面规格记录在 [gamejam/openspec/specs/gamejam/spec.md](gamejam/openspec/specs/gamejam/spec.md)。

`mirror-2610/` 的启动流程：

1. 先用 `three-bundle-loader.js` 加载 `three.bundle.js`，显示下载进度。
2. 加载完成后运行 `checkHtmlInCanvasSupport()`。
3. 支持且版本兼容：直接使用 WebGL 后端。
4. 支持但版本不兼容或无法识别：在加载层内显示方框面板，让用户选择继续 WebGL 或回退 SVG。
5. 不支持 HTML-in-Canvas：自动回退 SVG，并在加载层内提示可换用兼容 Chrome 并启用实验特性。
6. 加载层使用白底黑字、无圆角方框；加载层与预检面板都居中。预检出现时加载进度淡出、面板淡入（250ms），最终加载层以 250ms 淡出；在预检面板被回答或关闭前，加载层不会移除。
7. 内容区宽高各为页面的 72%（不支持镜面倒影的浏览器改为铺满整个视口，见「浏览器兼容与已知限制」）；`mirror.js` 的共享 `_relayout()` 统一把内容矩形量化到整数设备像素，误差小于 1 个 CSS 像素。
8. 内容区包含一个嵌套 Canvas 2D canvas（`content-field.js`）和一个五页幻灯片 deck：canvas 每帧填充实心 `center` 色并绘制从底部上升的暗色粒子；deck 直接位于 `#art` 内，因此文字、标题和分隔线都会参与镜像。canvas 不是 drawable 根，使用 `devicePixelRatio` 上限 2 的 backing store，不使用 CSS transform/filter。
9. 内容场第一帧渲染完成后才移除加载层；Canvas 2D 不可用时保留静态 `center` 色背景并跳过粒子场，deck 仍正常显示，mirror 仍正常挂载。
10. WebGL 默认使用 `renderScale: 1` 的 direct pass，镜像和中心内容在同一 1x pass 中完成，不再产生 0.5x 合成缝。低于 1 的 composite 路径仍保留：它使用 2 device px full-res edge skirt，用 body 纹理边缘像素覆盖低分辨率上采样缝。DOM seam guard 已移除。

### 浏览器兼容与已知限制

SVG 后端的镜像是「`backdrop-filter: url(#filter)` + `feImage` 位移贴图 + `feImage` 羽化蒙版」的组合。这条链路目前只有 Chromium 系能完整渲染：

| 引擎 | `backdrop-filter: url(#…)` | 镜像带 | 象限四色滤镜 |
| --- | --- | --- | --- |
| Chromium（WebGL 后端） | 支持 | ✅ | ✅ |
| Chromium（SVG 回退） | 支持，含 `feImage` | ✅ | ✅ |
| Firefox / Gecko | 只吃 GPU 加速的滤镜原语，`feImage` / `feDisplacementMap` 被静默丢弃 | ❌ 位移贴图与羽化蒙版都成了空图，整条链塌成“什么都不画” | ✅（只用 `feFlood` / `feBlend` / `feColorMatrix`） |
| Safari / WebKit | 完全不实现 `url()` 形式的 backdrop 滤镜 | ❌ | ❌ |

- **上游**：Gecko 缺 `feImage` / `feDisplacementMap` 的加速实现见 [bug 1896504](https://bugzilla.mozilla.org/show_bug.cgi?id=1896504)（NEW，P2，重复单 [1972363](https://bugzilla.mozilla.org/show_bug.cgi?id=1972363)；Mozilla 开发者的原话是“backdrop-filter 不支持绘制非 GPU 加速的滤镜，会退回 blob 失败”）；WebKit 见 [bug 245510](https://bugs.webkit.org/show_bug.cgi?id=245510)（NEW，P2，2026 年 7 月已有修复 PR 未合并）。
- **不是挂载方式的问题**：同一份 `feImage` 用普通 `filter:` 应用时 Firefox 正常渲染（那条路有 blob 回退）。本机探针确认：`feImage` 作为 backdrop 滤镜时，data URI、blob URL、同文档元素引用三种挂载全部渲染为空；换成 `feFlood` 的同结构滤镜则正常。所以 base64 → blob 的替换无效，`filterUnits` / 区域大小也不是原因（`feFlood` 用同样的整屏 `userSpaceOnUse` 区域照常着色）。
- **本版不做引擎特化实现**：理论上可以给 Gecko 加一条 `-moz-element(#content)` + 翻转 + `mask-image` 渐隐 + `blur()` 的反射层（本机验证过效果与 WebGL 后端几何一致），但那会引入 Gecko 专属合成路径与额外重绘成本；当前决定保持单一后端实现，等上游修复。
- **全屏 fallback**：启动时用 `checkMirrorBandsSupport()` 判定这条 backdrop 链路是否可用（Gecko 用 `-moz-element` 特性探测兜底 UA 伪装，WebKit 按引擎识别；iOS 上的 `CriOS` / `FxiOS` / `EdgiOS` 都按 WebKit 处理）。判定不可用时：预检面板换成「当前浏览器不支持镜面倒影」并提示改用 Chrome，`contentSize` 从 `72% × 72%` 换成 `100% × 100%`，内容铺满视口，`body[data-mirror-layout="fullbleed"]` 可供 CSS 与探针识别；同时 SVG 后端在 margin 为 0 时直接跳过位移贴图与蒙版（否则每次 resize 都要光栅化一张整屏 PNG），玻璃层也不挂 backdrop-filter。
- **全屏 fallback 的已知副作用**：封面 150% 的 sideview 插画和详情页右侧操作栏原本靠外侧 14% 留白吸收溢出，铺满后会被视口边缘裁掉；这一轮先接受，后续如需修可在 `body[data-mirror-layout="fullbleed"]` 下单独收边。
- **Firefox 下的实际表现**：deck、翻页、淡入淡出、粒子场、象限色片都正常，只是四周没有倒影带；页面没有降级提示，也不需要降级提示。
- **排查方法提醒**：Firefox 的截图接口（`--headless --screenshot`、CDP/BiDi `captureScreenshot`）不走合成器，`backdrop-filter` 在那条路上完全不渲染（连 `blur()` 都没有）。要判断滤镜是否生效必须抓真实屏幕（桌面截图），否则会把“截图路径不画滤镜”误判成“滤镜全挂”。

### Origin trial（HTML-in-Canvas）

`mirror-2610/index.html` 的 `<head>` 里固定放了一条 Chrome origin trial 的 `<meta http-equiv="origin-trial">`，用途是让**使用稳定版 Chrome 的普通访客**也能直接拿到 HTML-in-Canvas 的 `content="drawable"` / `requestPaint()` / `captureElementImage()` / WebGL2 `texElementImage2D()`，从而走 WebGL 后端，而不是被预检判为不支持后回落到 SVG。

- **token 内容**：`origin=https://ellia.cn:443`、`feature=HTMLInCanvas`、`isSubdomain=true`、到期 `2027-03-02T00:00:00Z`。也就是覆盖整个 `https://*.ellia.cn`，站点必须以 HTTPS 部署在该域下；换域（预发、预览、`127.0.0.1`）时 token 不匹配，Chrome 只会忽略它。
- **只加在这一页**：origin trial 的作用域是文档，只有用到该 API 的页面需要；`mirror-lab.html` 不带 token（且已不发布）。
- **为什么不做“仅 WebGL 后端注入”**：页面先 `checkHtmlInCanvasSupport()` 再决定后端，而脚本注入的 token 必须早于任何特性检测（OriginTrials 开发者指南 FAQ 16），因此按后端条件注入是循环依赖；静态 `<meta>` 天然覆盖所有分支，且在 SVG 路径上完全惰性。
- **预检逻辑不变**：`supported` 仍由特性探测决定，trial 只是让这些 API 存在；`HTML_IN_CANVAS_MIN_CHROME` 版本闸门保留（trial 不修 Chrome 155 的嵌套 canvas device-pixel 问题）。行为变化只有一点：参与了 trial 的 Chrome < 157 现在会进入“继续 WEBGL / 回退 SVG”对话框，而不是像以前那样静默回退。
- **续期**：token 过期或被浏览器拒绝时不会报错，页面回到今天的 SVG 回退路径（控制台可能有一条 warning）。到期前在 [developer console](https://developers.chrome.com/origintrials/#/trials/my) 续期并替换这一条 meta 即可；`gamejam/tools/probe_origin_trial.py` 会解码 token 并断言 origin、feature、子域标记与到期时间。

### 内容场

`mirror-2610/content-field.js` 用 Canvas 2D 绘制实心背景和上升粒子。

- **实心背景**：内容背景只有 `center` 色；没有深度带、渐变、矩形环、内开口线或 CSS 边框。mirror root 使用同一个 `center` 色；只有在 composite 模式下，WebGL 才使用 full-res edge skirt 重复 content 的真实边缘颜色。
- **上升粒子**：固定大小的粒子池按内容面积生成（面积 / 7000，限制在 24–120 个）。每个粒子的尺寸、深浅、速度、横向摆动和寿命独立随机；粒子从内容底部缓慢上升，随时间缩小并淡出，结束后回到底部重新淡入。初始化时粒子生命进度被均匀预热，首帧就有完整分布。
- **绘制方式**：粒子用预生成的径向渐变 sprite 画柔和边缘，再叠一个小实心核心；颜色固定为 `#242622`（`SURFACE.particle`），只在启动时构建一次 sprite。
- **运行节奏**：只要页面可见，rAF 就一直运行；鼠标停住、移出内容或完全不动都不会暂停。页面隐藏时停止，恢复可见时继续。`prefers-reduced-motion` 下只渲染一帧静态分布，不启动循环。
- **固定参数**：粒子尺寸 `1.2–4.2px`、速度 `16–38px/s`、密度面积 `7000px²`、DPR 上限 `2`；`PARTICLE_DEFAULTS` 与 `field.getState()` 仍可读到这些值和当前数量。
- **固定 feather**：两个后端都固定为 `72px`，没有运行时可调入口。
- **验证环境**：推荐使用 Chrome Beta 158 验证 WebGL。Chrome 155 等低于 157 的版本存在嵌套 canvas 的 device-pixel 缩放问题，页面会按现有预检提示并默认回退 SVG。

### 幻灯片 deck

内容区是一个五页的 deck，直接在 `#art` 内参与镜像。页面不再渲染之前的 `FIELD / SPECIMEN / INDEX / NODE` 占位容器。

- **五页内容**：封面、`象限`、`排行榜`、`作品详情`、`收尾`。封面左下是 `CEA GameJam` 与较小的 `2026.10` 同一基线，下一行是 `参赛作品展示`；右下是实际的 `ellia / sideview` 图像；最底部有一条 6px 黑边。第二页是四象限布局；第三页用两条竖线夹住可滚动队伍列表，左侧是 `评分排行` 主标题和 `Rank list` 副标题；第四页是作品详情版式，包含左侧作品名/说明栏、占位视频面板、右下角可隐藏操作面板和底部作品切换栏；第五页是收尾页，画面中间只有 CEA 字标和其下方弱化的占位信息，两条规则条变成穿过 content 左右边中点的 45° 斜切。
- **视觉规则**：黑字、透明背景、无圆角、等宽大写标签；封面不使用 header/footer 分隔线，文字也不带任何边框，全部为衬线体、左对齐；右下角是透明背景的 sideview 图像，底部有 6px 黑边。第二页同样不设 eyebrow/footer，以 3px 中心十字和四个无外框的象限文本构成版面。
- **翻页**：顶部左右角两个 40×34px 的方框按钮，只显示箭头，不参与镜像；滚轮、方向键、`PageUp`/`PageDown`、`Home`/`End` 也可切换。
- **全页指针圆环**：保留原生光标；五页的内容区都会在指针周围绘制浅灰圆环（`#9d9d9d`）。圆环是 deck 的直接子层，位于所有 slide 之下，因此在象限页仍会被四色滤镜着色；尺寸和描边随指针速度变化。
- **持久规则条**：封面底部黑边由两条重叠的纯色 `absolute` div 组成，位于 deck 层、所有 slide 之下，不受淡入淡出影响；超出 content 的部分由 `#deck` 的 `overflow:clip` 自然裁切。两条线的长度取内容宽高的两倍，旋转和移动过程中两端始终在内容外，避免看到线头。进入第二页时，一条平移到内容中心高度，另一条 `rotate(90deg)`，两者以 `720ms` transition 组成 3px 中心十字；进入第三页时分成 30% / 90% 两根竖线，夹住 60% 宽、整体右移的排行榜；进入第四页时两条规则各顺时针旋转 90°（从 90° 到 180°），分别落到 content 顶部和底部内侧，形成上下框线；进入第五页时再顺时针转 45°（180° → 225°），自重中心分别移到 content 右、左两边的中点：第四页的顶线向右就位成右上斜切，底线向左就位成左下斜切，两条线不会在中途交叉；返回封面时还原。第二页原有的分隔线 DOM 已移除。
- **内容层不滚动**：`#deck` 使用 `overflow:clip`（保留 `overflow:hidden` 作为回退），规则条超出的部分照旧被裁切，但 deck 不再是滚动容器——否则聚焦某个按钮时浏览器会把它左右挪动 1–2px，整个 content 随之偏移并在镜像边缘露出缝隙。
- **逐元素淡入淡出**：`js/effects/fade.js` 读取元素上的 `data-fade`、`data-fade-in-delay`、`data-fade-out-delay`（毫秒），用 Web Animations 逐个执行 opacity 动画，基础时长 `220ms`。
- **当前排版节奏**：封面按 `CEA GameJam` → `2026.10` → `参赛作品展示` → sideview 图像依次进入，持久规则条不参与淡入淡出；象限页按四个象限文本 → 中心 `镜` 依次进入；排行榜按 `评分排行` → 队伍列表 → `Rank list` 依次进入；作品详情页按左侧作品名/说明 → 视频面板 → 底部切换栏依次进入；收尾页按 CEA 字标 → 说明主行 → 说明副行依次进入。离开时使用更短的独立延迟。整组动画结束后才解锁翻页。`prefers-reduced-motion` 下直接切换。
- **文本间隙**：品牌与日期同一基线，行内间距约 `16–32px`；品牌/日期行与 `参赛作品展示` 之间约 `16–34px`。左文本与右图像之间使用固定响应式列距（约 `24–58px`），避免两列贴在一起。
- **布局**：`cqw`/`cqh` 相对内容尺寸；封面文字在左侧，图像绝对定位并贴紧 content 右下角。`--cover-bar-height` 固定为 `6px`；`--cover-bottom-gap` 固定为 `32px`，`--cover-text-y` 固定为 `0px`；`--cover-art-scale` 固定为 `1.5`（即 150%），缩放锚定右下角，因此图像变大后仍贴住 content 右下角、允许与左栏文本框叠在一起（图像左侧为透明）。图像元素向右额外偏移 `2px` 以避开贴边白缝，超出 content 的部分被裁切。图像保持 `1401/978` 比例并使用 `object-fit:contain`；窄屏时文字整体上移到图像上方，图像仍贴住 content 右下角。
- **文本视差**：`parallax.js` 挂载在封面文字、象限页文本、排行榜、作品详情页和收尾页上。封面品牌深度 `0.14`、日期 `0.26`、标题 `0.44`；象限标题深度 `0.22`、正文深度 `0.5`、中心 `镜` 深度 `0.9`；排行榜左侧两个标题共用 `0.36`，容器 `0.18`、卡片基础 `0.28`、悬浮卡片提升到 `0.68`；作品详情页左栏文本 `0.16`，视频面板与操作托盘同为 `0.52`（近层）；收尾页字标 `0.2`、说明 `0.34`；桌面最大位移 `24px`，窄屏按视口宽度缩放（最小 `8px`），模块自身再做平滑。
- **配置**：`Copy config` 的 `deck` 段报告页数、当前页、`fadeDuration`、`fadeMode` 和 fade 元素数量；`cover` 段报告 `barHeight`、`bottomGap`、`textY`、`imageSize`；`parallax` 段报告当前深度层，`quadrants` 段报告悬停象限、滤镜面板和圆环尺寸/速度参数。
- **已知问题**：Chrome Beta 的 WebGL 侧边镜像在切页后可能保留上一页的 DOM 残影；中心 content 和翻页状态正常。这是 HTML-in-Canvas 捕获记录刷新的问题，后续需要单独处理 `mirror.js` 的纹理刷新。

### 象限页

第二页（`data-slide="1"`）以页面中心为原点分成四个象限：左上 `时间`、右上 `主题`、左下 `限制`、右下 `评分`，中心是单独的 `镜`。

- **分隔线与外框**：中心横/竖分隔线为 `3px`；四个象限的标题和正文不再带矩形外框。每个文本组从象限中心向对应的外角偏移：水平约内容宽度的 `6%`，垂直约 `5.2%`（窄屏降到 `2.4%`），让中心更空。中心 `镜` 也不再带任何外框，保持单独的字形。
- **SVG 背板滤镜**：四个透明面板分别覆盖四个象限，使用 `backdrop-filter: url(#…)`。左上红 `#ff2b2b`、右上绿 `#00c853`、左下蓝 `#1f52ff`，都用 `feFlood + feBlend mode="screen"` 将深色墨迹推向对应颜色；白色在 screen 下保持白色，越深的像素着色越明显。右下用 `feColorMatrix saturate=0` 直接去饱和。颜色是高饱和混色，不是把每个像素强制替换成纯原色。四个面板带 `data-fade`，进入/离开第二页时以 `opacity` 跟随切页淡入淡出（`220ms`）；SVG filter URL 本身不做插值。
- **指针着色**：圆环位于四个滤镜面板下方，因此跨象限时会被对应颜色重新着色；中心没有方框，圆环会继续显示在 `镜` 字下方。原生光标始终可见，移出内容或进入按钮/调参面板时圆环隐藏。
- **圆环速度响应**：全页圆环共用同一套速度响应。静止或慢速时直径约 `34px`、描边约 `5.5px`；速度升高时直径增大到约 `82px`，描边减薄到约 `1.1px`。速度值经过平滑和衰减，停止后圆环回到小而厚；位置本身直接贴住指针。
- **悬停内容**：每个象限默认只显示衬线标题；指针移入后标题淡出，显示多行衬线正文，必要时自动换行。中心 `镜` 周围保留一块不可见死区，不触发象限悬停。中心 `镜` 位于四个滤镜下方，因此字会被红/绿/蓝/灰按象限切开着色。
- **字号**：第二页字号约为初版的 `1.5` 倍。桌面标题 `40.5–75px`、正文 `21–28.5px`、中心 `镜` `93–162px`；窄屏为 `27–45px`、`13.5–18px`、`60–96px`。
- **性能与后端**：四个背景滤镜会随粒子场和指针持续重绘；WebGL 与 SVG 后端都验证了滤镜、指针和镜像输出。

### 排行榜页

第三页（`data-slide="2"`）将排行榜整体右移，左侧中部纵向叠放大号 `评分排行` 与小号副标题 `Rank list`，中间偏右是可独立上下滚动的队伍列表。

- **框架**：两条持久规则条进入第三页后旋转成竖线，位于内容宽的 `30%` 与 `90%`，列表列宽 `60%`，整体右移；列表容器左右各留 `6–14px` 外边距，滚动条不会贴住竖线。左侧 `30%` 栏中纵向叠放两行标题并垂直居中：`评分排行` 为大号主标题（约 `29–76px`），`Rank list` 为小号、宽字距的灰色大写副标题（约 `14–22px`）；两者距左边缘约 `18–40px`，共用 `0.36` 视差深度。`≤700px` 时隐藏两行标题，规则移到 `4%` / `96%`，列表占 `92%`。
- **滚动轴**：排行榜 slide 设为 `overflow:visible`；列表 `overflow-x:hidden` 禁止横向滚动条，`overflow-y:auto` 保留纵向滚动。左右 padding 预留 `14–26px`，足够容纳卡片放大和 parallax 位移，避免横向裁切可见内容。外层 mirror content（`#art` / `#deck`）继续 `overflow:hidden` / `overflow:clip`，负责内容边界的镜像裁切。
- **队伍卡片**：启动时从 `data/ranking.json` 读取 15 支队伍，并在 mirror 挂载前渲染。每张卡左栏纵向放 `#排名`、并列标记和单项奖 tag（左栏不额外描边），中栏为作品名/队伍名，右栏为 2×2 四项均分和右下角的综合分；卡片保持透明背景和 1px 黑框，列表上下滚动。
- **强调色**：使用 `--red:#d84a33`。第 1–3 名的排名数字、第一名综合分、单项奖 tag 的边框与文字、以及对应单项奖的小分标签/数值使用强调色；其他文字保持黑/灰。
- **滚动优先**：指针位于两条竖线之间时，window 捕获阶段的 wheel 处理器把滚动量累加到目标值，再用 rAF + 指数插值推进 `scrollTop`，并 `preventDefault` / `stopPropagation`；不再依赖事件最终落在哪个卡片或 DOM 上，也不会触发 deck 翻页。原生滚动、滚动条拖动或键盘操作会中断插值并重新同步目标值。`prefers-reduced-motion` 下直接跳转。离开该区域后恢复翻页。
- **悬浮**：卡片使用 `scale` 放大到 `1.035`，不加白底；仅保留 1px 描边。卡片基础视差深度 `0.28`，悬浮时切到 `0.68`，离开后恢复；排行榜容器自身深度 `0.18`，左侧两个标题共用 `0.36`。卡片不再可聚焦，点击透明区域不会保留“选中”层级。
- **尺寸**：桌面卡片宽约 `490–590px`、最小高度约 `108px`；`≤1120px` 时卡片改为上下两行（分数组移到标题下方，综合分仍靠右下），`≤700px` 使用窄屏字号并隐藏左侧标题栏。
- **排行数据**：`mirror-2610/data/ranking.json` 由 `tools/convert_ranking.py` 从 `assets/mirror-26/cea-submissions-2026-codejam-rating-20261106-113938.csv` 生成。JSON 按名次保存队伍（同分并列同一名次并标记 `tied`）、四项均分、`totalScore`（0–40）、`overallScore`（0–10）、被评次数和单项奖；顶层 `awards` 保存四个奖项的最高分获奖者及随后三名。转换时按最新提交去重、忽略自评，评委提交参与打分但评委队伍不进入排名。重新生成：`.venv\Scripts\python.exe gamejam\tools\convert_ranking.py`。
- **当前剔除**：`对的对的`（teamId `14`）不参与排名，其收到的 `18` 条评分也不计入；最终为 `15` 支队伍、`255` 条有效评分。剔除名单维护在 `convert_ranking.py` 的 `EXCLUDED_TEAMS`，JSON 的 `excludedTeams` 和 `stats.excludedTeamCount` / `excludedRatingCount` 会记录该状态。

### 作品详情页

第四页（`data-slide="3"`）是单件作品的详情版式，全页统一使用衬线字族，作为排行榜之后的作品展示入口。

- **框架**：持久规则条进入第四页后，两条线都从第三页的 `90°` 顺时针转到 `180°`，即各旋转 90°，分别停在 content 顶部和底部内侧（`3px` 线宽），形成上下框线。主体为 `24% / 76%` 两列，底部作品切换行从内容高的 `10%` 降到 `7%`；上下框线之间的整个 content 都是作品轮换区。
- **左侧介绍**：左栏不再绘制整张卡片边框。作品名是 1px 黑框、文字居中，随后是**该作品的说明文本**，最后用 1px 横线分隔 `来自：` 与队伍名；说明、作品名和队伍名都随当前作品从 `data/works.json` 读取。整组内容（标题 → 说明 → 队伍）作为一块在左栏垂直居中，说明文本不再拉伸去填补空位，`detail-intro-meta` 也不再用 `margin-top:auto` 顶到底部。四边内边距收紧为上下约 `22px`、左右约 `23px` 的对称内缩，长队伍名在窄栏中自动换行。
- **视频框**：主列中放置 1px 黑框的视频面板，顶部/底部各留约 `13.4%` 行高，左侧留约 `2.7%` 主列宽；右侧只留约 `3.8%` 主列宽，使视频右框距离 content 右边框约 `30px`。面板内清空了所有装饰文字，视频源来自该作品记录的 `video.src`（当前测试数据统一指向 `mirror-2610/assets/video-placeholder.mp4`，`988×586`、约 `10.9s`）。视频 `autoplay muted loop playsinline`、`object-fit:contain`，由 JS 按 `988 / 586` 计算出 `contain` 后的实际尺寸写入 `.detail-video-stage`，因此画面永不超出面板、也不留内部 letterbox。
- **无视频状态**：作品没有 `video` 时，元素不会被创建、面板加上 `is-video-empty`，`aria-label` 改为“暂无作品视频”，stage 仍按 `988 / 586` 占位（切换回来不跳动）。面板内部显示占位内容：居中的 `暂无视频` 与宽字距的 `NO CLIP YET`（`rgba(10,10,10,.46)` / `.3`），外层仍由四角标框住。
- **四角标**：面板内边距（桌面约 `24px`、窄屏 `11px`）里放四个 2px 笔画、约 `29px` 臂长的 L 形角标。角标挂在 video 的 stage 上，位置为 `-0.5 × 角标尺寸`，即角标外角与面板边框保持约 `10px` 的最小距离、同时贴住视频四角；视频换尺寸或换页时随 stage 一起移动。角标画在视频外侧的留白环里，因为镜像会把视频作为独立图层合成在 canvas 之上，画在视频内部的装饰会被盖住。
- **播放控制**：视频只在第四页激活时 `play()`，离开该页时 `pause()`，避免后台解码；`prefers-reduced-motion` 下暂停在首帧。**音频默认开启**（`muted = false`）：若浏览器因缺少用户手势拒绝有声自动播放（`NotAllowedError`），自动降级为静音播放，不会卡在加载态。
- **延迟加载**：页面启动时**不创建任何 `<video>`**，第一段视频只在第四页真正激活时才请求；离开第四页时把当前 video 的可见类移除（`<video>` 是独立合成层，不会跟随祖先的 `visibility:hidden`，必须由元素自身隐藏，否则会像早前那样盖到封面上）。
- **faststart 要求**：视频必须是 `moov` 在 `mdat` 之前的 faststart MP4，否则浏览器要下载完整个文件才能读到时长与首帧，表现为“进度 0% 直接跳 100%，且必须全部下完才播放”。运行素材已用流拷贝重封装（`-c copy -movflags +faststart`，体积与画质不变）：`powershell -File gamejam\tools\make-faststart.ps1`；重新导出投稿视频时也应保留该标记。
- **加载覆盖层**：视频不再是“换 src”，而是每个作品一个独立 `<video>`（池），全部叠放在 `.detail-video-window`（`overflow:hidden`）里，只有 active 那个可见。切换时白色遮罩滑入（`560ms`），**方向跟随切换方向**：向前从下往上（`101% → 0`，`-101%` 退场），向后从上往下（`-101% → 0`，`101%` 退场）；遮罩内是 `LOADING`/`READY`、作品名、进度条与百分比；`canplay` 之后**先从遮罩下方换好 video 元素并开始播放**，再让遮罩向上滑出（`→ -101%`，`520ms`），因此观众看到的是“遮罩移开即新视频”，不会先看到旧画面或空帧。已加载过的作品切回时走 `300ms` 的短版出入场，保持节奏一致。
- **进度语义**：进度条按 `buffered.end(last) / duration` 显示已缓冲比例（与早期实现一致）；**`canplay` 未触发时进度条为强调色**（`--red`），触发后转为黑色，并在遮罩退场前保持。`duration` 未知时退回不确定扫动条；加载失败时遮罩停在原地、转为强调色错误态（`Clip unavailable / 加载失败`），**不会移开遮罩**，也不会切换 video；此时仍可继续切到别的作品，成功加载后才恢复出遮罩。
- **卡顿叠层**：播放中触发 `waiting` / `stalled` 时，视频上会**立即**出现一层 `72%` 半透明白底 + `LOADING` 的叠层（无过渡、`pointer-events:none`），`playing` / `canplay` / `seeked` / `pause` 时立即消失；离开第四页也会立刻收起。层级为 `deck(0) < stall(1) < veil(2)`，并且 `stall` 只在 `phase === 'ready'` 且遮罩不在场时才会显示——切换过程中它永远不会盖在加载遮罩之上。
- **切换锁定**：遮罩出入场期间忽略滚轮、箭头与点击切换，滚轮累加值一并清空；遮罩停在“加载中”时仍允许继续切换，此时不重放出入场，只把名称与进度条换成新目标。滚轮手势锁为 `900ms`，避免长动画期间连续跳件。
- **加载池**：切换只改可见元素，**不取消**旧任务的加载（只 `pause()`），所以切走的视频仍会在后台加载完成。池上限 3（当前 + 最近 2 个已就绪），超出时回收最久未用的“已就绪”元素，**从不回收加载中的元素**；被回收的作品再次打开会重新加载，同源同 URL 一般命中 HTTP 缓存，因此仍走一次冷加载的遮罩。
- **音量条**：动作按钮上方是一条与按钮同宽的白色音量条（`音量` 标签 + 强调色滑杆 + 百分比），与动作面板共用一个 `.detail-tools` 容器、同一套显示规则——指针悬停视频面板时两者一起浮现，托盘固定时一起常驻。滑杆写入当前 `<video>` 的 `volume`，新加载的作品继承当前音量。显示条件用的是 `:has(:focus-visible)` 而不是 `:focus-within`：鼠标点过滑杆后焦点仍在 input 上，旧的 `:focus-within` 会让整条工具栈被“钉”住、不再响应鼠标进出，必须点到别处才恢复；现在只有键盘聚焦才会常驻。
- **操作面板**：原右侧 `Featured` 浮层卡已移除。视频右下角是一个无底色、无边框、无标题栏的按钮托盘，横向宽度约主列的 `22.5%`（最小 `150px`、最大 `310px`），右边与下边各向外错开约 `18px` / `30px`，仍留在 content 内；`right` 额外留出深视差（`0.52 × 24px`）的位移余量，托盘收起时也不会越界。
- **按钮可用性**：三个按钮由作品记录里的链接决定——`links.download` / `links.play` / `links.project` 有 URL 时按钮启用并记住 `data-href`（点击在新标签页打开），为空时 `disabled` 并显示为灰化占位。`下载` 使用强调色（`--red` 的边框与文字）作为主操作，其余保持黑色；启用态悬停整块反色——下载填充强调色、其余填充黑色，文字转白，边框/底色/文字同步过渡 `160ms`；禁用态白底降为 `62%` 不透明，中性按钮边框/文字退到 `22%` / `34%` 黑，下载按钮退到 `34%` / `56%` 强调色。托盘默认隐藏：指针悬停视频时浮现，继续移到托盘凸出的外角不会消失，离开视频与托盘后收起；点击视频、或聚焦视频后按 `Enter` / `Space` 可固定托盘（触屏与键盘），`Esc` 或点击视频外关闭，视频上的 `aria-expanded` 同步更新。
- **滚动切换**：指针位于上下两条框线之间时，window 捕获阶段的 wheel 处理器把滚动累积为作品切换：阈值 `40px`、手势锁 `900ms`，一次手势切换一件作品，`preventDefault` 后不会翻页。指针移出 content 后恢复 deck 的滚轮翻页。左右箭头仍可逐件切换，切换时标题、队伍、页数指示和 slide 标签一起更新。
- **边界不循环**：作品列表不再首尾相连。边界处只把 `slideIndex ± 1` 交给 deck：第一个作品向前会翻回 `排行榜` 页；最后一个作品向后则进入收尾页。deck 本身不回环，因此在收尾页继续向后 `goToSlide` 直接返回 `false`、停在原地，不会跳回封面。`select(index)` 提供了直接跳转（用于深链与探测）。
- **切换动画**：左栏作品名、说明、队伍名三段各 `560ms` 上浮淡入，彼此错开 `80ms`（`0 / 80 / 160ms`）；配合遮罩 `560ms` 入场 + `520ms` 出场，单次冷切换约 `1.1s`，切回已加载作品约 `0.6s`。`prefers-reduced-motion` 下三段动画直接跳过。
- **字号（本轮放大）**：说明正文 `13–17.5px`（原 `11–14px`），动作按钮中文 `15–21px`（原 `13–18px`），英文副标 `9–11px`（原 `7–9px`），音量条标签与数值同步为 `8–11px` / `9–11px`。
- **页脚**：页脚不再重复作品名或奖项，只保留全宽居中的作品切换器。左右箭头是一份独立的按钮样式，尺寸与等宽字形对齐 deck 翻页按钮（桌面 `40×34`、字号 `16px`，窄屏 `36×32`、字号 `15px`），但静止时无填充、无边框；悬停只画出 1px 黑框、不填充白底，并带 `160ms` 的 `border-color` 过渡；不使用顶栏的“黑底白字”反色。中间是 15 段等长的 `-` 形页数提示（每条是一个 `button`）：短划之间不留间距，只有当前作品的短划改为实黑且高度是其余的两倍（`4px` vs `2px`）、其余保持 `22%` 黑；每条的可点/可悬停区间为 `28–34px` 高（约原来的 2 倍），悬停或键盘聚焦非当前短划时其内部线条从 `2px` 拉高到 `24px`（约 3 倍），点击直接跳到对应作品。切换器距底部框线保留固定约 `10px` 的间距（`clamp(7px,1.5cqh,12px)`）。作品名集中在左侧标题框，页数已由页脚短划承担。
- **响应式**：`≤700px` 时改为标题/说明、视频、页脚三行堆叠，比例为 `24% / 69% / 7%`；上下框线仍保留，页数提示随可用宽度伸缩，轻点视频即可展开托盘，页面不产生横纵溢出。
- **视差**：本页复用 `js/effects/parallax.js`，左栏文本 `data-parallax="0.16"`（远层），视频面板升级到 `0.52`（近层），操作托盘与视频同层，因此始终贴合视频右下角；与其余页面共用 `24px` 最大位移和 `9` 平滑系数。
- **动效边界**：结构线与视频框边界保持稳定；本页参与逐元素淡入淡出、作品切换动画和指针视差，`prefers-reduced-motion` 下关闭位移动画与视差。

#### 作品媒体数据（`data/works.json`）

每件作品的说明、视频与三个动作链接都按 `teamId` 与 `ranking.json` 对齐，一个队伍一份记录。文件由 `tools/generate_works.py` 生成（当前是测试数据），页面在 mirror 挂载前加载：

```json
{
  "schemaVersion": 1,
  "generatedAt": "2026-11-08T19:51:22+08:00",
  "generator": "tools/generate_works.py",
  "source": "mirror-2610/data/ranking.json",
  "note": "测试数据：视频与链接均为占位，等待真实投稿替换",
  "works": [
    {
      "teamId": 7,
      "workTitle": "镜界",
      "teamName": "吴彦组",
      "description": "《镜界》由「吴彦组」在 48 小时内完成……",
      "video": { "src": "assets/video-placeholder.mp4" },
      "links": {
        "download": "https://example.com/cea-gamejam-2026/works/07/build.zip",
        "play": "https://example.com/cea-gamejam-2026/works/07/play",
        "project": "https://example.com/cea-gamejam-2026/works/07"
      }
    }
  ]
}
```

- `teamId` 必填并与 `ranking.json` 的 `teamId` 对应；`workTitle` / `teamName` 仅作校对用，页面仍以 `ranking.json` 为准。
- `video` 可以是 `null` 或 `{ "src": "…" }`；`src` 相对 `mirror-2610/`，为空即无视频面板。
- `links.download` / `links.play` / `links.project` 可以是 URL 或 `null`，分别控制对应按钮是否可用。
- 重新生成：`.venv\Scripts\python.exe gamejam\tools\generate_works.py`；`--check` 只校验文件是否为最新。

### 收尾页

第五页（`data-slide="4"`）是 deck 的最后一页，不放任何可操作控件：画面正中只有 CEA 字标，字标下方是一行衬线说明和一行更小的等宽副信息。

- **斜切框线**：两条持久规则条在这一页各顺时针再转 45°（`180° → 225°`），并把自身中心移动到 content 短边的中点——于是每条线与该短边的交点就是线自身的中心，也是那条边的中点。**顶线（`sheetRuleA`）移到右边中点成为右上斜切，底线（`sheetRuleB`）移到左边中点成为左下斜切**：两条线各自朝原来的方向继续走，不交叉。越过 content 的部分由镜像复制到四周，形成右上与左下两处 45° 斜切（`3px` 线宽，与其余页面一致）；斜线长度仍是内容宽高的两倍，旋转过程中两端始终被裁切，看不到线头。不做竖屏适配。
- **字标**：`assets/mirror-26/cea-logo.svg` 通过 `page.toml` 的 `include` 进入构建；SVG 使用 `fill: currentColor`，因此直接跟随页面文字色（`#0a0a0a`），不需要另做反色版本。宽度 `clamp(150px, 21cqw, 330px)`，保持 SVG 的 `315.5 / 108` 比例，水平居中。
- **弱化信息**：字标下方是两行文案——衬线主行 `苏州大学计算机爱好者协会 · 2026.10`（`rgba(10,10,10,.46)`、`13–20px`）与等宽副行 `由 DarkskyX 设计并制作 · 含AI生成内容`（`rgba(10,10,10,.32)`、`9–12.5px`、`0.05em` 字距；不再做大写转换，中文与 `DarkskyX` 都按原样显示）。两行都是 `data-fade` 元素，进入时与字标错开 `150ms` / `210ms`；换成真实的谢幕信息只改这一处。
- **重心**：`.slide-end` 取消内边距并用 `place-items: center` 居中，整组（字标 + `20–44px` 间距 + 两行说明）的视觉中心就是 content 中心。
- **视差与降级**：字标 `data-parallax="0.2"`、说明 `0.34`，与其余页面共用 `24px` 最大位移和 `9` 平滑系数；`prefers-reduced-motion` 下切页与规则条都直接跳到终态。

### Resize 结构遮盖层

页面顶部有一层全屏的构成主义结构图，`z-index:78`，位于 deck 控件之上、启动层之下，不参与镜像，也不拦截指针。

- **触发**：监听 `mirror` 的 resize 生命周期——`resizeStart` 淡入、`resizing` 保持并更新尺寸、`resizeEnd` 后排定淡出。单独的 `resize` 事件只用来更新读数/尺寸，不再触发显示，因此 `mirror.refresh()` 不会误触发遮盖层。初始挂载阶段不显示；启动层移除后才启用。mirror 的 resize 去重窗口为 `500ms`。
- **节奏**：`resizeStart` 时以 `500ms` 淡入；持续 resize 期间保持；`resizeEnd` 后保持 `475ms`，再以 `250ms` 淡出——从 `resizeEnd` 到完全消失约 `0.72s`，是原来 `950 + 500` 的一倍时间的一半（探针会测量这个窗口：从窗口 resize 起约 `1.2–1.3s`，其中含 `500ms` 去重）。
- **内容**：白底、细黑外框；按 mirror 区域划分为中央 content 矩形和上、下、左、右四条反射带；中央矩形上方和左侧各有一条带端点的尺寸线，实时显示内容 CSS 宽高；右下角显示 `resizing...`。四个反射带和中心分别用淡灰英文衬线标签标识，不加网格、斜线或额外图形。
- **尺寸更新**：`resizeStart` 开启一个 rAF 测量循环，在 resize 生命周期内每帧用容器当前宽高调用 `mirror.previewLayout(width, height)`，即时解析 `72%` 内容尺寸并更新标注；`resizing` 事件也会刷新。它不依赖 debounce 后才落地的 `#art` 矩形，`resizeEnd` 停止循环并用真实矩形收口。
- **降级**：`prefers-reduced-motion` 下改为直接显示/隐藏。

实现位于 `mirror-2610/index.html` 的 `#structureVeil`、`showStructureVeil()` 和 `hideStructureVeilSoon()`。

### 设备像素布局

`mirror.js` 的 `_relayout()` 生成统一的 layout：

```js
{
  width, height, ax, ay, aw, ah,  // CSS px
  dpr,
  device: { width, height, ax, ay, aw, ah } // integer device px
}
```

SVG filter、WebGL canvas/render target、纹理捕获和 hit testing 都从同一份 `device` 数据派生。页面只传入 `contentSize: { width: '72%', height: '72%' }`，不再自行做 DPR 取整。

WebGL 默认走 1x direct 路径；`renderScale < 1` 时仍可走 composite 路径：低分辨率镜像 target + 1x body target，最后用 linear upscale 合成。合成阶段额外绘制一圈 2 device px 的 full-res edge skirt，UV 取 body 纹理边缘内侧 1.5 texel，用真实边缘颜色盖住 low-res 边界。

### 固定参数（原调参面板已移除）

`mirror-2610/index.html` 不再有悬浮的 `TUNE / 2610` 面板，原先可调的两项已写进样式表：

- 封面底部黑边 `--cover-bar-height: 6px`（原默认 `3px`）
- 封面图像 `--cover-art-scale: 1.5`（即原 `Image Size 150%`），缩放锚定 content 右下角

其余参数本来就是固定值，现在只作为常量存在：

- 实心背景 `#ffffff`、粒子 `#242622`：`SURFACE` 常量，随 mirror 一起传入，不再经过 `localStorage`
- feather `72px`、blur `2.00`；WebGL `renderScale 1` / `contentScale 1`；SVG `mapScale 0.1` / `maxMR 1920x1080`
- 封面 `Gap` 固定 `32px`、`Text Y` 固定 `0px`；第二页十字与收尾页斜切固定 `3px`

诊断信息（DPR、内容尺寸、后端类型、canvas 输出尺寸）仍可通过 `window.__mirrorHome.getState()` 读取。

## 构建

要求 Python 3.11+，只使用标准库，不需要安装额外依赖。

```powershell
# 查看页面列表
python build.py --list

# 全量构建到 dist/
python build.py

# 只构建一个页面
python build.py gamejam

# 构建并显示细节；把页面 warning 当作错误
python build.py gamejam --strict --verbose

# 先清空 dist/ 再全量构建（可清理已删除页面的残留）
python build.py --clean
```

也可以显式使用虚拟环境：

```powershell
.\.venv\Scripts\python.exe build.py
```

输出结构：

```text
dist/
└─ gamejam/
   ├─ index.html
   ├─ assets/
   │  └─ mirror-26/
   │     └─ cea-logo.svg
   ├─ mirror-2610/
   │  ├─ index.html
   │  ├─ content-field.js
   │  ├─ assets/
   │  └─ data/
   ├─ js/
   │  └─ effects/
   │     └─ mirror.js
   └─ libs/
      └─ three/
         ├─ three.bundle.js
         ├─ three-bundle-loader.js
         └─ vendor/
```

`mirror-2610/mirror-lab.html` 是开发/探针专用页面，`page.toml` 已把它排除在构建之外，`gamejam/build.py` 也会在它泄漏到 `dist` 时报错。

构建行为：

- `dist/<page>/` 会以 staging 目录整体替换，不会留下上一次构建的旧文件。
- 单个页面构建失败时，不会替换已有的 `dist/<page>/`。
- 默认只保证当前构建的页面目录是干净的；要删除已移除页面的残留，使用 `--clean`。
- `--out DIR` 可修改输出目录，但会拒绝项目根目录、页面源码目录以及 `.git/`、`.venv/` 等保留目录。
- 当前构建只做复制和校验，不做 HTML/CSS/JS 压缩或指纹化。

## 页面清单 `page.toml`

```toml
name = "gamejam"          # 必须与目录名一致
title = "ELLIA PAGES — GAMEJAM 2026"
entry = "index.html"      # 构建后必须存在，且必须被 include 命中

include = [
  "index.html",
  "mirror-2610/**",
  "assets/mirror-26/cea-logo.svg",  # 收尾页字标
  "js/effects/**",
  "libs/three/**",
]

exclude = [
  "libs/three/src/**",
]
```

- `include` 是必需项，相对于页面目录，支持 `*`、`**` 等 glob。
- 目录被 glob 命中时会递归收集其中的文件。
- `exclude` 使用 `fnmatch` 匹配相对于页面目录的路径。
- `page.toml`、页面 `build.py`、`.gitignore` 和 `tools/` 不会自动进入构建，除非被 `include` 明确包含。
- 当前 `gamejam/build.py` 会额外检查并阻止这些源码文件泄漏到 `dist/`。

## 页面级 `build.py`

页面目录内的 `build.py` 是可选的，由根目录 `build.py` 动态导入。它不会被复制到 `dist/`。

可定义两个钩子：

```python
def prebuild(ctx):
    """复制前执行，用于校验源文件或补齐构建输入。"""

def postbuild(ctx):
    """复制完成后执行，可修改 staging 目录。"""
```

`ctx` 提供：

- `ctx.page`：页面元数据（`slug`、`entry` 等）
- `ctx.source`：页面源码目录
- `ctx.stage`：本次构建的 staging 目录
- `ctx.out_root`：输出根目录
- `ctx.strict` / `ctx.verbose`
- `ctx.log(message)`：仅在 `--verbose` 时输出
- `ctx.warn(message)`：记录警告；配合 `--strict` 会使构建失败

钩子抛出异常会终止该页面的构建，并保留旧的 `dist/<page>/`。当前 `gamejam/build.py` 会检查 three 运行时文件、检测过期的 `three.bundle.js`，并防止源码文件进入产物。

## 新增页面

1. 在仓库根目录创建页面目录，例如 `new-page/`。
2. 添加 `new-page/page.toml`，至少包含 `name`、`entry` 和 `include`。
3. 需要额外校验时添加 `new-page/build.py`。
4. 添加 `new-page/.gitignore`，忽略页面本地日志、缓存和临时产物。
5. 运行 `python build.py --list` 确认发现，再运行 `python build.py new-page`。

## 开发服务器

构建系统不负责启动服务器。开发时直接服务 `gamejam` 源码目录：

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory gamejam
```

- 页面目录：<http://127.0.0.1:4173/>
- mirror 主页：<http://127.0.0.1:4173/mirror-2610/>
- mirror 实验页：<http://127.0.0.1:4173/mirror-2610/mirror-lab.html>（只在源码树里，`dist` 中不存在）
- 构建产物预览：把 `--directory` 改为 `dist/gamejam`，并换一个端口。

页面测试脚本：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\verify_render_scale.py
.\.venv\Scripts\python.exe gamejam\tools\verify_resize_hooks.py
.\.venv\Scripts\python.exe gamejam\tools\probe_mouse_fx_lab.py

# 内容场（粒子/双后端/DPR/减少动态/回退）
.\.venv\Scripts\python.exe gamejam\tools\probe_content_field.py

# 幻灯片 deck（翻页/淡入淡出/双后端/移动端）
.\.venv\Scripts\python.exe gamejam\tools\probe_deck.py

# origin trial token（解码 origin/feature/到期时间 + 无 flag 启动冒烟）
.\.venv\Scripts\python.exe gamejam\tools\probe_origin_trial.py

# 倒影能力判定 + 全屏 fallback（UA 判定表 / Chromium 保持 72% / 伪装 Gecko 走全屏）
.\.venv\Scripts\python.exe gamejam\tools\probe_bands_fallback.py

# 收尾页视觉抽查（截图写入 .dsh/，可加 --large / --backend=svg）
.\.venv\Scripts\python.exe gamejam\tools\shot_end.py

# 封面固定参数抽查（截图写入 .dsh/，参数为 宽 高 dpr）
.\.venv\Scripts\python.exe gamejam\tools\shot_cover.py
```

前三个脚本默认访问 `http://127.0.0.1:4173/mirror-2610/mirror-lab.html`（因此要用源码目录起服务）；内容场、deck 与 origin trial 探测访问 `http://127.0.0.1:4173/mirror-2610/`，默认使用 Chrome Beta。

## three 运行时 bundle

`gamejam/libs/three/three.bundle.js` 是生成文件，正常构建直接复制它，不需要 Node。修改入口或 vendor 后重新生成：

```powershell
.\gamejam\tools\build-three-bundle.ps1
```

该脚本使用 `npx esbuild@0.25.0`，首次运行需要 Node/npm 和网络。页面构建钩子会在 `libs/three/src/three-bundle-entry.js` 比 bundle 新时给出警告。

## 素材重绘

`gamejam/assets/mirror-26/ellia-sideview.svg` 由同目录的 PNG 重绘而来，是白底、双灰披风、近黑人物和深红缎带的五色分层 SVG。封面运行时使用 `gamejam/mirror-2610/assets/ellia-sideview-flat-clipped.png`，由 `gamejam/assets/mirror-26/ellia-sideview-flat-clipped.png` 复制而来。收尾页直接引用 `gamejam/assets/mirror-26/cea-logo.svg`（已加入 `page.toml` 的 `include`）；该字标用 `fill: currentColor`，因此会跟随页面文字色。生成脚本：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\trace_sideview.py
```

脚本只使用标准库完成 PNG 解码、调色板分层、灰边/杂点清理、Taubin 轮廓平滑和 Bézier 拟合；目标是流畅的矢量线条，而不是逐像素描边。`--flow` 控制轮廓平滑强度（灰色布料默认是人物层的两倍），`--epsilon` / `--tolerance` 控制简化与拟合误差，`--stroke` 用来补层与层之间的亚像素缝隙。

`--render` / `--diff` 会额外使用 Playwright + Chrome Beta 渲染预览并报告逐层 IoU：

```powershell
.\.venv\Scripts\python.exe gamejam\tools\trace_sideview.py --render .dsh/ellia-preview.png --diff .dsh/ellia-diff.png
```

## 手动描改器

`gamejam/tools/trace-editor.html` 是一个不依赖构建的 SVG 描改页面：钢笔点击/拖拽画贝塞尔曲线，点回起点闭合后按当前颜色填充；参考 PNG 可调透明度、正片叠底和置顶；支持图层、撤销/重做、localStorage 草稿、JSON 工程与 SVG 导出。

用现有的开发服务器打开即可（页面通过相对路径读取 `assets/mirror-26/ellia-sideview.png`）：

```powershell
.\.venv\Scripts\python.exe -m http.server 4173 --directory gamejam
```

<http://127.0.0.1:4173/tools/trace-editor.html>

操作要点：

- `P` 钢笔：点击加点，按住拖动拉出对称切线；点回第一个点闭合，`Enter` 结束，`Esc` 放弃当前路径。
- `V` 选择：拖动节点/控制柄；双击线段插入节点；双击节点切换尖角/平滑；`Delete` 删除；方向键微移。
- `Space` + 拖动平移，滚轮缩放，`F` 适配窗口，`H` 隐藏参考图，`1–5` 快速换色。
- 钢笔模式下色板只决定**下一个区域**的颜色；选择模式下点色板才会改当前选中区域。已闭合区域也可以在右侧属性面板改色、填充规则和层级。
- 右侧“参考图”支持透明度、正片叠底（白底透出棋盘格）和置顶；在已填区域上继续描时建议勾选置顶，或把正片叠底关掉。
- 草稿自动保存在浏览器 localStorage；“导出 SVG”可以带白底或透明；编辑器节点、控制柄、选中线不会进入导出。

## 为什么使用 Python

- 页面都是静态文件，构建主要是校验、复制和少量页面钩子；Python 标准库足够。
- 仓库里的浏览器测试和探测脚本已经是 Python，构建与测试共用同一个运行环境。
- 不需要为普通构建引入 `node_modules`、包管理器或前端框架。
- 只有 three bundle 需要 esbuild；它被隔离在 `gamejam/tools/build-three-bundle.ps1`，不影响日常构建。

如果以后需要资源指纹、HTML 压缩或真正的 JS 打包，可以在现有入口上增加步骤，或再引入 Vite/Astro；目前没有必要。
