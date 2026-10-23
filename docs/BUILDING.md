# 使用与构建

## 公共 Python 工具

在仓库根运行：

```sh
PYTHONPATH=shared python3 -B -m unittest discover -s tests -v
python3 -B tools/check_publication.py
```

`tools/inspect_rom.py` 默认只核对 SHA 与大小。需要读取一条流时，另外传 `--offset 0x... --mode jp` 或 `--mode cn`；模式不能省略。未附带字形表，输出 token 而不是伪造中文解码。调用 CFG 解析器时需自行提供经过版本校验的 opcode 宽度表，未知指令不猜长度。

## 盒子显示源码（不是完整补丁构建器）

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
