# 权利与来源

本仓库中的项目自有代码与文档按 MIT 发布。该许可不覆盖原游戏 ROM、游戏素材、存档、未包含的翻译文本、字体、图块或第三方工程。

公共核心的初始代码来自项目自有 `fr_foundation_v1/fr_pipeline` 中的 `rom.py`、`text.py`、`events.py`、`script.py`。本次逐文件审阅后保留实现；不是整个历史执行框架的重新发布。对应来源与哈希见 `docs/SOURCE_PROVENANCE.json`。

后续补入的编码器、字库页表和 glyph source codec 来源于本项目的叶绿工具源码，公开版增加边界门禁；单字实验只使用原项目手绘的测试笔画。它们不包含供体字模、系统字体、Unicode 来源字表或完整译文。现用字表中存在大量可逐字节追溯到美版汉化供体的字模记录，详见 `docs/LEAFGREEN_ORIGIN.md`；这些素材的再分发许可尚未核实，不属于本仓库 MIT 授权范围。

叶绿1.0末端构建器仅包含项目自有的读取／验证／重定位逻辑；标题数据从调用者本地供体读取，不随源码分发。工具能读取某种资源不等于获得该资源的再分发许可。

事件结构、控制码长度和脚本操作数布局参考了 [pret/pokefirered](https://github.com/pret/pokefirered) 的格式研究（`include/global.fieldmap.h`、`include/characters.h`、`src/text.c`、`asm/macros/event.inc`）。这里记录参考来源；未打包该工程源码、游戏数据或工具链，也不把它们重新许可为 MIT。

GNU Arm 工具链、Python、mGBA 等外部依赖不随仓库分发，各自许可证仍适用。没有把工程内的第三方字体／译文／工具目录批量复制进来；以后引入第三方代码必须逐文件核实并保留其许可及署名。

font_pack.py及cn_glyph.s为项目自有的资源适配／四图块算法整理，复用既有codec和页内布局，不携带原游戏或供体字形。调用者传入字形的source字段只是来源声明，不代表本项目已核验其许可。公开测试和文档示例仅使用项目独立绘制的简单笔画。

firered/patches/tm_names.s原样来自项目BUILD0100的自有routes.s。tests/tm_cpu.c及tm_copy.s是独立编写的合成测试，不含原游戏StringCopy或任何ROM数据；mGBA仅通过调用者本地库链接，库和MPL许可的mGBA源码不随本仓库再分发。当前355条名称仅在调用者文件中校验，未随源码上传或重新许可。

Pokémon 等名称属于各自权利人。发布补丁或技术源码不等于获得原游戏内容的再分发许可。

cn_main_production.s、cn_small_production.s及两版glyph_metrics／分流入口整理自项目自有汇编和构建逻辑；不包含被调用的原生图块例程。火红旧入口的末端指针已参数化为现行分流地址；普通解码器合入现用字宽／高度覆写，具体来源与变更见SOURCE_PROVENANCE.json。字模、译文、小字宽度表均未随此批分发，MIT不覆盖这些外部资源。

新增width_scanners、width_alias、火红电脑字体和叶绿货币字体入口来自项目自有实现，按现行代码合入已存在的宽度别名调用；七组叶绿游标／ID配对不包含对应译文正文。tests/width_cpu.c是独立编写的生成内存测试，不含原游戏续程、字体或翻译文本。已知叶绿回退隐患随真实实现公开，未以源码整理为名静默修正游戏。
