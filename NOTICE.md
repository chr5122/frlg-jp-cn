# 权利与来源

本仓库中的项目自有代码与文档按 MIT 发布。该许可不覆盖原游戏 ROM、游戏素材、存档、未包含的翻译文本、字体、图块或第三方工程。

公共核心的初始代码来自项目自有 `fr_foundation_v1/fr_pipeline` 中的 `rom.py`、`text.py`、`events.py`、`script.py`。本次逐文件审阅后保留实现；不是整个历史执行框架的重新发布。对应来源与哈希见 `docs/SOURCE_PROVENANCE.json`。

事件结构、控制码长度和脚本操作数布局参考了 [pret/pokefirered](https://github.com/pret/pokefirered) 的格式研究（`include/global.fieldmap.h`、`include/characters.h`、`src/text.c`、`asm/macros/event.inc`）。这里记录参考来源；未打包该工程源码、游戏数据或工具链，也不把它们重新许可为 MIT。

GNU Arm 工具链、Python、mGBA 等外部依赖不随仓库分发，各自许可证仍适用。没有把工程内的第三方字体／译文／工具目录批量复制进来；以后引入第三方代码必须逐文件核实并保留其许可及署名。

Pokémon 等名称属于各自权利人。发布补丁或技术源码不等于获得原游戏内容的再分发许可。
