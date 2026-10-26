# 从日版原版到游戏内显示：首句实验

这是第一个把原版、调用者自备字形和自定义一行文字接起来的实验入口。它替换新游戏大木博士的第一段，后续对白仍是日文。

**不是当前2.3汉化的构建器，也不是通用中文引擎。** 实验会缩短原第一段并加一次按键等待，不能作为完整剧情译文发布。不要用于正式游玩存档，不提供ROM下载。

## 运行

需要Python≥3.10、GNU Arm binutils，以及自己合法持有的精确日版Rev0。输入SHA沿用[原版入口](EDIT_ORIGINAL.md)的两枚固定身份。

先按[字库流程](FONT_PIPELINE.md)的示例生成build/my_glyphs.json（独立手绘“中”的简单测试笔画），再运行：

```sh
# 默认只在内存中构建和检查。
python3 -B tools/build_original_probe.py --game leafgreen-jp-rev0 --original /path/to/BPGJ-original.gba --glyphs build/my_glyphs.json --text '中中中'

# 需要运行实验时，显式指定新文件；已有文件和输入原件均不可覆盖。
python3 -B tools/build_original_probe.py --game leafgreen-jp-rev0 --original /path/to/BPGJ-original.gba --glyphs build/my_glyphs.json --text '中中中' --output build/leafgreen-probe.gba

# 火红单独核对本版消费者；不靠固定地址差猜测。
python3 -B tools/build_original_probe.py --game firered-jp-rev0 --original /path/to/BPRJ-original.gba --glyphs build/my_glyphs.json --text '中中中' --output build/firered-probe.gba
```

不在PATH中的工具链可通过--arm-prefix指定，例如/path/to/arm-none-eabi-。输出前检查完整原版身份、原跳转、首段消费者与解码器哈希、原引用、新池FF、实际差异和保护区；写出后重读并核对两个输入未变。

打开新实验ROM，从头进入新游戏，翻过开场说明页，到大木博士首句。应看到自绘测试字；按A／B继续后回到日文对白。不要加载或创建存档，也不要把实验文件当作正式汉化发布版。

## 明确支持的范围

- 只替换首句的一行，1～14个已经在输入字库分配的私有字符；12×12度量，最多168px墨迹预算。
- 不接受原生字母／标点、换行、翻页、动态姓名或任何用户控制符。构建器自行加入FONT_MALE和WAIT／END，避免未经验证的场景扩张。
- 首段经原版StringCopy复制到显示RAM。包含FF字节的glyph ID（如0x01FF）在这一路径会被原生复制提前截断，因此本实验明确拒绝，**不会声称通用扫描已经兼容**。其它编码工具能产生该ID不等于所有原生消费者都支持。
- 不安装通用测宽、占位符展开、动态名称、菜单、帮助小字或战斗修复；本行的固定原生窗口不依赖新的通用测宽。原生非目标文字保持原分支。

## 接入与安全边界

本次直接从两版原版各自核对了首段代码、StringCopy调用和打印参数：

| 游戏 | 首段文本字面量槽 | 原文本指针 | 消费者范围（文件偏移） |
|---|---|---|---|
| 火红Rev0 | 0x130104 | 0x081AA211 | [0x1300CC,0x130124) |
| 叶绿Rev0 | 0x1300DC | 0x081AA1ED | [0x1300A4,0x1300FC) |

两版公共RenderText接入位置0x5814的8字节均核对前像。使用BX跳板，不借用低地址字体空隙：叶绿旧实验使用的0x1DB3A8在火红原版里并非全零，不能照搬。

新增实验独占窗口[0xB00000,0xB40000)只对精确原版有效，完整继承守卫、未用字模槽和FF尾；禁止把该窗口当作当前汉化版空闲区。布局为首16B守卫、代码0xB00010起、配置0xB00400、页表0xB00440、首句0xB00800、字库页0xB04000起。只改原跳转、该版首句字面量及这些新载荷，原生日文字库、字宽、存档代码、slot1和ROM头不变。

F7接入同时要求真实模板fontId=4、当前字节位于目标显示缓冲内，且整份RAM显示串与只读实验文本完全相同，才走新的四图块核心。模板+4是windowId，fontId在+5，不能混用。其它文字包括原生F7仍走原版分派；不能把本实验扩大到所有RAM字符串。

新汇编采用ARM7TDMI／Thumb1，没有固定返回地址猜读写。配置和原生回调仍由该版适配器提供，不是通用地址承诺。

## 验证和未完成项

合成测试覆盖错误原版、跳转／字面量／消费者／回调身份、非FF池、边界／重复／裁切、首句容量、FF内嵌ID拒绝、新文件写出和保护区。GNU Arm工具链不存在时汇编测试明确SKIP。

构建器本身永远报告runtime=UNOBSERVED，不能凭构建日志冒称游戏显示通过。实际运行证据另记在[验证记录](VALIDATION.md)。本实验尚无Delta、GBARunner3或真机验收，也不是全游戏回归；完整原版中文引擎仍需通用字宽／扫描、多个字体档位、动态缓冲和完整资源编排。
