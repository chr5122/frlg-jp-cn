# 日版火红／叶绿汉化 · FRLG JP→CN

火红和叶绿共用的开源工具与部分汉化修复源码，自有代码／文档采用[MIT](LICENSE)许可。项目为非官方技术项目。

**当前可以直接运行工具测试，尚不能只凭本仓库和原版ROM构建完整汉化。** 不提供ROM下载，不包含存档、完整译文、字库、游戏图块或第三方反编译工程。具体边界见[公开范围](docs/PUBLICATION_SCOPE.md)。

## 快速开始

需要Python 3.10或更新版本。纯Python部分仅用标准库，无需pip、make、模拟器或游戏文件：

```sh
git clone https://github.com/chr5122/frlg-jp-cn.git
cd frlg-jp-cn
python3 -B tools/check.py
```

Windows可将python3替换为python。检查入口先跑合成测试，再检查发布文件和私人信息；失败返回非零，不上传任何内容。完整入门与无素材示例见[开始使用](docs/GETTING_STARTED.md)。

## 你可以做什么

| 目标 | 入口 | 范围 |
|---|---|---|
| 学习／改进解析和验证工具 | shared/frlg/、tests/ | token、指针、事件、脚本、编码、字模codec等；需显式输入模式 |
| 核对本地ROM身份／读取token | tools/inspect_rom.py | 只读，输入自己合法持有；没有ROM下载 |
| 直接修改自己的日版原版 | tools/patch_rom.py | 按审核过的字节清单生成新文件；不依赖历史汉化父版，不含完整汉化清单 |
| 准备自己的中文字库 | tools/build_font.py、shared/patches/cn_glyph.s | 自备字形→字库页／字表及参数化ARM7解码核心；尚无原版安装器 |
| 从原版运行一行显示实验 | tools/build_original_probe.py | 两版首句限定接入；自备字形，无历史父版，不是通用引擎或完整汉化 |
| 编译两版盒子显示包装源码 | firered/patches/、leafgreen/patches/ | 生成ARM7TDMI／Thumb1载荷，不自动安装进未知ROM |
| 重放指定历史增量 | leafgreen/rebuild_*.py、firered/recap_species_range.py | 严格固定父版与资源；不是当前游戏的统一构建器 |
| 从原版构建当前完整汉化 | 尚未提供 | 缺失项和推进顺序见依赖与路线图 |

- [依赖与可运行范围](docs/DEPENDENCIES.md)：哪些已具备，哪些还缺资源／接口。
- [直接修改原版](docs/EDIT_ORIGINAL.md)：双版本固定原版入口、清单格式、写出和验证边界。
- [自备字形与解码核心](docs/FONT_PIPELINE.md)：无供体字库的资源接口、编码器连接及尚缺的安装步骤。
- [原版首句显示实验](docs/ORIGINAL_PROBE.md)：把自备字形接到两版新游戏首句，附严格限制和验证边界。
- [构建说明](docs/BUILDING.md)：具体工具的参数与适用版本。
- [路线图](docs/ROADMAP.md)：按成熟功能整理源码，再补当前构建流程。
- [验证记录](docs/VALIDATION.md)／[设备兼容性](docs/COMPATIBILITY.md)：测试证据和未覆盖范围。

## 项目方向

优先让贡献者能看懂、运行和改进现有功能；随后整理当前版本所需的最小构建流程与外部资源接口。**不再把逐个倒查旧FIX作为开源前置条件。**

既有[叶绿起源](docs/LEAFGREEN_ORIGIN.md)和[1.0历史调查](docs/LEAFGREEN_1_0_LINEAGE.md)保留作按需参考，不是普通使用者必须依次完成的教程，也不是最新游戏构建指南。部分历史入口会复现当时已知错误，文档已有警示，不能直接作为现行补丁使用。

## 源码快照与游戏版本分开

当前公开盒子显示源码和baseline.json最初核验的历史快照如下；**这不是最新游戏版本列表**，游戏后续更新不会自动改变已有工具的适用SHA：

| 游戏 | 公开代码的历史验证快照 | ROM SHA-256 |
|---|---|---|
| 火红日版 | 2.2.2 / BUILD0109 | `807c995fb637e7decc86566cf43a56e0d571d8a15a3cbcad2de81229e8bbd669` |
| 叶绿日版 | 2.2.2 / R87 | `69bf635f1936846aa4fbf320ecf8c5579b681451c20644902608751c597f3f33` |

合成测试通过不代表全游戏、全部联机或NDSL＋GBARunner3通过。不要修改预期SHA来让不适用的ROM强行通过。

## 参与贡献

先读[贡献约定](CONTRIBUTING.md)。欢迎小范围bug修复、合成反例、易用性和文档改进；问题、功能建议、PR均有模板。报告只写版本／SHA／步骤和脱敏日志，不上传ROM、SAV、即时存档、译文包或字库。

MIT仅覆盖有权许可的自有代码／文档，不授予游戏、商标或未包含素材的权利。[来源与权利说明](NOTICE.md)记录第三方参考和未核清依赖。本项目与任天堂、Game Freak、The Pokémon Company无隶属或授权关系。
