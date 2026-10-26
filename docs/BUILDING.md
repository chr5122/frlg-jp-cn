# 使用与构建

第一次使用请先看[开始使用](GETTING_STARTED.md)和[依赖表](DEPENDENCIES.md)。本页是具体入口参考；历史FIX部分不是要求按编号执行的当前构建流程。项目主线见[路线图](ROADMAP.md)，暂无“原版→当前完整汉化”的统一命令。

## 公共 Python 工具

在仓库根运行：

```sh
python3 -B tools/check.py
```

`tools/inspect_rom.py` 默认只核对 SHA 与大小。需要读取一条流时，另外传 `--offset 0x... --mode jp` 或 `--mode cn`；模式不能省略。未附带字形表，输出 token 而不是伪造中文解码。调用 CFG 解析器时需自行提供经过版本校验的 opcode 宽度表，未知指令不猜长度。

## 盒子显示源码（不是完整补丁构建器）

自备字形打包和新增ARM7解码核心见[字库流程](FONT_PIPELINE.md)。make asm现在也生成cn_glyph载荷；示例链接地址不是ROM分配许可，尚无原版引擎安装器。

安装 GNU Arm binutils 后，可把两份自有汇编构建为独立代码载荷：

```sh
make asm
```

输出在忽略的 `build/`。火红链接起点 `0x08EDA810`、叶绿 `0x08FFC110`。对应完整预留窗分别为 `[0xEDA800,0xEDAC00)` 与 `[0xFFC100,0xFFC300)`；不能把前后守卫或 FF 尾部给别的修复复用。

火红依赖既有显示 alias `0x08FFB3F0`；叶绿依赖 `0x08745A50`。源码中地址是这次指定版本的地址，不是原版通用接口。不提供把它们打进未知 ROM 的泛用脚本；完整 hook 前像、资源继承及父版身份缺失时必须停止。

## 火红 BUILD0107→0108 增量

这是已存在名称映射器的边界修复：内部物种有效集合 `1..251`、`277..411` 共 386 种；`252..276` 是旧占位，`412` 是蛋。不要拿全国图鉴编号 `386` 当内部物种编号上限。

父版必须是 SHA `392d177d3ed996aa74c7906be1a4ae7da5417a714419c7ad1309400d02eba85f` 的 BUILD0107；该文件不随仓库提供。

```sh
python3 -B firered/recap_species_range.py --parent /path/to/BUILD0107.gba
# 默认只在内存中验证结果；要另存才传 --output，且拒绝已有目标文件：
python3 -B firered/recap_species_range.py --parent /path/to/BUILD0107.gba --output /path/to/NEW_BUILD0108.gba
```

这只产生 0108 范围修复，不含后续图标居中，不是完整 2.2.2 构建命令。输入永不覆盖，输出只写新路径；不要用于别的汉化版。

## 叶绿起点单字实验（不是完整汉化）

这个小实验从精确 BPGJ Rev0 原版直接构建，不需要美版汉化供体、字库文件或译文。使用项目自己绘制的测试字笔画和从原版读取的 native lookup 表；只改一个原生字形槽，原有日文文本未翻译。它用于复现早期研究方法，不能应用到 R87，也不能当作对全局替换字形的推荐方案。

```sh
# 默认在内存中构建并检查，不落盘 ROM：
python3 -B leafgreen/experiments/first_glyph.py --original /path/to/BPGJ-original.gba
# 需要生成实验 ROM 时，另外指定全新输出路径：
python3 -B leafgreen/experiments/first_glyph.py --original /path/to/BPGJ-original.gba --output /path/to/new-experiment.gba
```

预期输出 SHA `09c7969f96ef067813fdee07d558dfa28aec177d451ba4c7db58e58a1ddc7694`。实际差异 36 B，限制在四个原生字模数据片段；不改指令、字宽或存档。原来使用该字形的日文位置会显示测试字；这是实验的预期副作用，**不是可游玩的汉化发布版**。本批只验证 native lookup 像素回读，运行画面仍为 UNOBSERVED。

## 不携带资源的叶绿文本编码器

`shared/frlg/encode.py` 使用本地 CSV 字表，格式沿用 `unicode,glyph_id,status`，正式构建仍需来源记录和实际字模。仓库仅用合成字表做测试，不提供正式字表。

```sh
PYTHONPATH=shared python3 -B -m frlg.encode --charmap /path/to/local-map.csv --text '中文{NL}{PLAYER}！{END}' --hex
```

没有分配的字符、重复 Unicode／gid、未知 token、END 后内容和 RAW 字节绕过均拒绝。`font_pages.py` 只计算历史页表范围，不负责批准新资源分配；不得将其常量当作完整台账。

## 叶绿1.0末端重建（不是从原版开始）

从这里起主要是历史复现参考，普通工具开发无需先执行。严格输入版本、素材依赖及历史错误警示仍适用，不应串联猜测当前版本构建顺序。

用户需自行提供精确父本与本地字表。默认只在内存中重建并检查最终SHA：

```sh
# FIX582 -> FIX583 / 最终1.0：
python3 -B leafgreen/rebuild_1_0_tail.py --from fix582 --parent /path/to/FIX582.gba --charmap /path/to/local-map.csv
# FIX581 -> FIX582 -> FIX583：另需原版与本地供体，仓库不提供：
python3 -B leafgreen/rebuild_1_0_tail.py --from fix581 --parent /path/to/FIX581.gba --original /path/to/BPGJ-original.gba --donor /path/to/local-BPGE-CN.gba --charmap /path/to/local-map.csv
```

需要保存时添加 `--output /path/to/new-output.gba`；已有文件／输入文件一律不覆盖。输出对应最终1.0，不是2.2.2。输入SHA和独立归档验证方式见 [1.0调查](LEAFGREEN_1_0_LINEAGE.md)。

## 历史构建清单只读调查

在本地持有原工程材料的机器上运行：

```sh
python3 -B tools/audit_build_lineage.py --analysis /path/to/local-project/analysis --include-fix-reports --artifact-dir /path/to/local-project/output --target-sha256 900b5247f04a30402ae35e3336c398006305efa0b7f01bdc3de1cdc28023c11c --summary-only
```

工具不执行任何历史脚本，只提取明确的ROM文件名与身份字段。默认不读取产物；提供 `--artifact-dir` 才核验该目录直接包含的 `.gba`，不读取 SAV/state。返回的哈希边仍是声明，不是重建通过；缺失身份保持未知。

退出0只表示调查报告成功生成，`json_errors`、未知身份和 `complete_rebuild_proven=false` 仍须逐项查看；不能把退出0称为完整构建门禁通过。

存在 `parents[]` 的记录将额外列出 `merge_base` 与每个 `branch`；任一父身份缺失、重复、冲突或集合结构未知，整条依赖保持待核，不能退回只算基底的“通过边”。`target_unresolved_frontier` 是无法继续沿完整声明边展开的SHA，不是漏译项目数。

## FIX561 三输入合并（独立归档重放已验证）

用户自行提供精确FIX558、FIX559及“四到七岛”FIX560：

```sh
python3 -B leafgreen/rebuild_merge561.py --base /path/to/FIX558.gba --save /path/to/FIX559.gba --islands /path/to/FIX560-islands.gba
# 可另加 --compare /path/to/FIX561.gba，与留存产物逐字节比较。
```

本入口没有写出选项，不会改任何输入。它只合并既有分支，不会从原版构建分支本身，也不替代译文／指针／字形的语义验证。所需SHA、同编号分支陷阱和本批测试边界见 [1.0调查](LEAFGREEN_1_0_LINEAGE.md)。已使用本地归档的三个精确父本与独立子版逐字节比较；公开CI只用合成字节测试，不下载ROM。

## FIX557～559：固定历史输入的局部复现

```sh
# FIX556 ->557：无需外部译文或字表；只交换WAIT与标点顺序：
python3 -B leafgreen/rebuild_557_559.py --stage 557 --parent /path/to/FIX556.gba --compare /path/to/FIX557.gba
# FIX557 ->558，以及FIX558 ->559：还需本地原始清单和兼容字表：
python3 -B leafgreen/rebuild_557_559.py --stage 558 --parent /path/to/FIX557.gba --manifest /path/to/fix558_manifest.json --charmap /path/to/local-map.csv --compare /path/to/FIX558.gba
python3 -B leafgreen/rebuild_557_559.py --stage 559 --parent /path/to/FIX558.gba --manifest /path/to/fix559_manifest.json --charmap /path/to/local-map.csv --compare /path/to/FIX559.gba
```

三个入口均无写出选项。输入父本、清单、CLI字表与最终产物均固定完整SHA；不是随意清单打补丁工具。FIX558/559从外部清单重新编码文本，验证指针前像、保留前缀的相对位移、FF池、原地容量、写入不重叠、差异数量和整枚最终SHA。不会读取子版作为构建来源，`--compare`只作可选末端比较。

原始清单包含完整译文，**本仓库不提供**；字表两个允许身份见源码，已证兼容的备份不等于当次构建的原始资源快照。本入口不重跑旧脚本的条目发现／可达性算法，也不为当前ROM批准旧资源池重用。不能用于火红、R修订版或未知汉化。

补充谱系时可在前述调查命令中加：

```sh
--extra-record docs/lineage_verified/fix557.json --extra-record docs/lineage_verified/fix558.json --extra-record docs/lineage_verified/fix559.json
```

这些是后补验证记录，未回填原始清单。累计七份补证后严格身份前沿到FIX552；仍非从原版开始的完整构建链。

## FIX555／556：无需外部译文或字表的布局复现

```sh
python3 -B leafgreen/rebuild_layout555_556.py --stage 555 --parent /path/to/FIX554.gba --compare /path/to/FIX555.gba
python3 -B leafgreen/rebuild_layout555_556.py --stage 556 --parent /path/to/FIX555.gba --compare /path/to/FIX556.gba
```

入口读取固定父本的生效指针和完整CN token流：555仅删一处WAIT后的冗余NL；556仅把两条活文本里的16个旧私有标点转换为原生字节。文字、字模和字表均不随工具提供；不会从子版抽取差分。共享解析器保证参数／字形内部碰巧出现的FA、FE等字节不被当成布局符。

只在已核对的历史FF窗重定位，逐个旧指针、源长度、转换次数、目标长度与整枚输出SHA均固定；无写出选项。FIX556原清单的old_stream字段沿用更早版本地址，实际FIX555指针指向另一处；新入口使用真实生效地址0xE3805C／0xE380A8，不把过时元数据当作前像证据。

复现谱系累计需五个补证参数；在上方三个参数后追加：

```sh
--extra-record docs/lineage_verified/fix555.json --extra-record docs/lineage_verified/fix556.json
```

555／556独立归档结果见 [布局重放摘要](LEAFGREEN_LAYOUT_REPLAY.json)。固定旧池不等于批准在当前游戏复用；不能应用到现行火红或叶绿R版。

## FIX553／554：措辞清单与历史布局回归

```sh
# FIX552 ->553：本地原清单包含13条译文，仓库不提供：
python3 -B leafgreen/rebuild_revisions553.py --parent /path/to/FIX552.gba --manifest /path/to/fix553_revisions_manifest.json --charmap /path/to/local-map.csv --compare /path/to/FIX553.gba
# FIX553 ->554：沿用既有工具文件名，新增固定554入口：
python3 -B leafgreen/rebuild_layout555_556.py --stage 554 --parent /path/to/FIX553.gba --compare /path/to/FIX554.gba
```

均无写出选项。553固定父本／原清单／CLI字表／最终SHA；重新编码每条旧全文并与父ROM完整一致后，再验证旧指针、FF及4 B前探、目标边界与新全文。复现历史省略号成对编码，只显式适配当次已知FD01／FD06和FC0B5601，不开放共享编码器的RAW绕过。原脚本的发现条目和旧行宽判据未重跑。

**554会复现历史标点回归**：删掉两处WAIT后冗余NL时，旧编码器把原生标点又转成私有字形。此行为后来由556修正；本入口用于历史字节证明，不是对当前游戏的新修复，不能跳过556后直接当发布版使用。

前述五个补证参数后继续加：

```sh
--extra-record docs/lineage_verified/fix553.json --extra-record docs/lineage_verified/fix554.json
```

独立归档比较和方法边界见 [本批摘要](LEAFGREEN_REVISIONS_REPLAY.json)。累计七份后补记录，不回填原清单，严格身份前沿到FIX552。
