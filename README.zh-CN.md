# GameCrafter 项目主页

**GameCrafter: An Agentic Framework for Scalable Multi-Gameplay Game World Generation**

[English](README.md)

本仓库是研究项目的静态展示网站，包含六扇区交互式 3D 总览、方法图、八个已录制游戏场景，以及高清多场景 teaser。

## 本地打开

Windows、macOS 和 Linux 均可使用 Python 3：

```sh
python3 serve.py
```

Windows 也可以运行 `python serve.py`。浏览器打开 `http://127.0.0.1:8765/`；端口占用时添加 `--port 8766`。交互 3D 需要支持 WebGL 的现代浏览器。请通过本地 HTTP 服务访问，不要直接双击 `index.html`。

网站不需要构建、API 密钥或外部资产服务器。Three.js、模型、贴图和展示媒体均已包含。

## 展示内容

- 首页六个微缩场景：樱花庭院、霓虹街区、沙漠庭院、雪地哨站、地中海庭院和水下基地。
- 结果区保留八个案例，包括此前的修道院与蒸汽工厂。
- 展示各案例已有的探索、Boss 战、三个视角与五种视觉输出。
- 可旋转缩放的场景模型，以及真实 Unreal Engine 截图和视频。
- 方法图和此前归档的中英双语 v1.0 框架源代码下载。

首页圆盘是用于展示的代表性 Web 微缩景观，不是完整 UE 关卡导出。结果截图和视频来自实际 UE 录制。同组的五种模态使用相同帧与相机；不同视角的独立录制不宣称同步。网页深度图和语义图是展示预览，不能代替原始科学数据。

## 更新与部署

`src/worlds.js` 定义场景与圆盘配置，`src/media.json` 定义视频、相机、模态和全景模型。方法图与 teaser 位于 `assets/figures/`。保留相对路径，即可部署在 GitHub Pages 的仓库子路径下。场景深链接示例：`?scene=neon_switchyard#results`。

在 GitHub 仓库的 **Settings → Pages** 中选择 **Deploy from a branch**，使用 `main` 分支的根目录。`.nojekyll` 使网站按普通静态文件发布，不需要 Git LFS 或构建流程。展示资产总量约 530 MiB，全景模型仅在用户点击后加载。

原始游戏项目与生产记录单独保留。素材来源与许可见 [ATTRIBUTION.md](ATTRIBUTION.md)，历史录制颜色说明见 [CAPTURE_NOTES.md](CAPTURE_NOTES.md)。依赖库许可不自动覆盖生成或用户提供的媒体资产。
