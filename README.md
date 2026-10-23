# 日版火红／叶绿汉化 · FRLG JP→CN

火红和叶绿共用的开源仓库。这里发布经过整理的项目自有工具、部分显示修复源码和技术文档，自有代码采用 [MIT](LICENSE) 许可证。

**这是首批源码公开，不是完整 2.2.2 构建包。** 当前不包含 ROM、存档、原游戏素材、完整译文、字库或第三方反编译工程；仅凭本仓库和原版 ROM，暂时不能重建完整汉化版。尚未公开的依赖和原因见 [公开范围](docs/PUBLICATION_SCOPE.md)。不提供 ROM 下载，也不接受通过 issue 上传 ROM／存档。

## 已公开内容

- `shared/frlg/`：从项目执行框架抽出的公共核心：固定 SHA 身份门禁、指针／范围检查、差分白名单、JP/CN 显式 token 解析、地图事件结构与脚本控制流走查。
- `firered/patches/`、`leafgreen/patches/`：两版冒险回顾盒子名称的独立入口 ARM7TDMI／Thumb1 包装源码。
- `firered/recap_species_range.py`：火红 BUILD0107→0108 的物种范围修复，固定父版身份、默认只验证、不覆盖输入。
- 两版 2.2.2 的 SHA-256 记录、合成反例测试、发布内容检查和 CI。
- 从叶绿汉化起点整理的编码器、字库页表／source codec，以及不需要供体资源的单字实验。源头证据与尚未闭合的构建区段见 [叶绿起源追溯](docs/LEAFGREEN_ORIGIN.md)。
- 叶绿480份历史构建记录的只读适配器、[1.0构建链调查](docs/LEAFGREEN_1_0_LINEAGE.md)，以及锁定父版的 FIX582→最终1.0 复现入口（仍非原版到完整汉化）。

## 快速验证

需要 Python 3.10 或更新版本；公共 Python 工具只依赖标准库。

```sh
PYTHONPATH=shared python3 -B -m unittest discover -s tests -v
python3 -B tools/check_publication.py
python3 -B tools/inspect_rom.py --help
```

核对自己合法持有的文件（只读）：

```sh
python3 -B tools/inspect_rom.py --manifest firered/baseline.json --kind release --rom /path/to/local.gba
```

汇编与增量修复的准确使用范围见 [构建说明](docs/BUILDING.md)，本次实际运行结果见 [验证记录](docs/VALIDATION.md)。测试不需要任何游戏文件；CI 不上传或下载游戏文件。

## 版本与兼容性

| 游戏 | 本次源码整理对应的正式版本 | ROM SHA-256 |
|---|---|---|
| 火红日版 | 2.2.2 / BUILD0109 | `807c995fb637e7decc86566cf43a56e0d571d8a15a3cbcad2de81229e8bbd669` |
| 叶绿日版 | 2.2.2 / R87 | `69bf635f1936846aa4fbf320ecf8c5579b681451c20644902608751c597f3f33` |

这里的游戏版本号不是公共工具的版本号，也不意味着完整源码链已公开。GBARunner3 的镜像执行约束、设备验证边界以及未覆盖内容见 [兼容性](docs/COMPATIBILITY.md)。**不宣称全游戏、全部联机或 NDSL＋GBARunner3 已验证。**

## 参与贡献

请先读 [贡献约定](CONTRIBUTING.md) 和 [权利与来源说明](NOTICE.md)。优先事项：补齐可独立复现的源码依赖链、核清字库与译文授权、增加消费者证据与硬件回归，而不是增加未经验证的“全部通过”统计。

本项目为非官方技术项目，与任天堂、Game Freak、The Pokémon Company 无隶属或授权关系。MIT 仅覆盖仓库中有权许可的自有代码和文档，不授予游戏、商标或未包含素材的权利。
