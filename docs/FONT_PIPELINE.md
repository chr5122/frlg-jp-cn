# 自备字形→字库页／字表→解码核心

这批把中文显示的资源依赖拆出来：调用者可以使用自己绘制或有明确许可的字形，不必提供历史汉化ROM或美版汉化供体。另可生成独立小字页和宽度表，并核对普通／小字编号是否一致。

**当前不是通用原版中文引擎安装器。** 打包器不读取ROM，汇编只生成可调用的解码核心；另有[两版首句限定实验](ORIGINAL_PROBE.md)，但通用前缀接入、私有码字宽／占位符扫描和完整译文编排仍未完成。不能把生成的字库或代码直接复制到任意原版地址就算安装完成。

## 字形输入

Python≥3.10，标准库即可。JSON结构：

```text
{
  "schema": 1,
  "source": "由调用者描述来源、作者和许可；工具不核发素材许可",
  "glyphs": [
    {"unicode": "中", "glyph_id": "0x0100", "pixels": 一个16行×16列整数矩阵}
  ]
}
```

上面的pixels是结构说明，不是可直接解析的JSON。每个像素为0、1、2，沿用已公开source codec；0为空白底，1／2为两种非空源像素状态。右侧／底部12以外的像素必须为0，否则拒绝，避免12×12度量截断笔画。页和槽的排列复用font_pages.py，编码复用glyph_codec.py，不另造图块格式。

Unicode字符和ID一一对应；ID范围0x0000～0x0AFF。重复字符／ID、原生字符（如字母、数字和原生标点）、控制字符、花括号、代理码点均拒绝。已识别为原生的字符继续由encode.py编码，不分配私有字模。

下面只用项目独立绘制的简单测试笔画构造输入，**不是正式字体**。先自行创建build目录，再运行：

```sh
python3 -c 'import json; p=[[0]*16 for _ in range(16)]; p[1][1:9]=[1]*8; p[5][1:9]=[1]*8; p[10][1:9]=[1]*8; [p[y].__setitem__(4,1) for y in range(12)]; print(json.dumps({"schema":1,"source":"Independently drawn test marks, MIT","glyphs":[{"unicode":"中","glyph_id":"0x0100","pixels":p}]}))' > build/my_glyphs.json
python3 -B tools/build_font.py --glyphs build/my_glyphs.json
python3 -B tools/build_font.py --glyphs build/my_glyphs.json --output-dir build/my_font
```

第一条构造输入；第二条只在内存校验；第三条输出到全新目录，已有目录一律拒绝，不自动覆盖或合并。生成的输入和字库请留在忽略的build目录或仓库外，不提交私人资源。

## 输出及编码器连接

- page_XX.bin：该页的0x4000字节。仅生成有字形的页；每页256槽，未分配槽全FF。
- blank_page.bin：完整0x4000字节全FF回退页；缺页应显式指向它，不能用空指针。
- charmap.csv：unicode,glyph_id,status；状态为allocated，**不会因为成功打包就冒称字形已验收**。
- manifest.json：输入和输出的SHA、大小及生成结果；不复制输入的私人来源字符串。来源／许可说明仍须自行保留，不是工具已完成版权审核。

```sh
PYTHONPATH=shared python3 -B -m frlg.encode --charmap build/my_font/charmap.csv --text '中。{END}' --hex
```

示例ID0x0100预期为f70100adff。生成的私有F7流**仍不能直接交给未安装对应解析器的原版**。

## 自备小字和普通字编号配对

小字需要调用者独立绘制的16×16像素矩阵，每项在普通字输入字段之外再提供整数`width`（0～16），表示该字的水平前进宽度。非零像素须位于x < width、y < 13；宽度0仅可用于无墨迹字形。这个打包约束防止截断和占用下一个字符的位置；它不是对所有历史字模的兼容性保证。

下面用前述独立测试笔画演示流程；复制普通字笔画只是合成样例，实际小字应根据显示效果单独绘制：

```sh
python3 -c 'import json; d=json.load(open("build/my_glyphs.json")); [g.update(width=10) for g in d["glyphs"]]; print(json.dumps(d,ensure_ascii=False))' > build/my_small_glyphs.json
python3 -B tools/build_small_font.py --glyphs build/my_small_glyphs.json --normal-charmap build/my_font/charmap.csv
python3 -B tools/build_small_font.py --glyphs build/my_small_glyphs.json --normal-charmap build/my_font/charmap.csv --output-dir build/my_small_font
```

提供`--normal-charmap`时，字符集合及每个glyph ID必须与小字**完全一致**；缺字、增字或编号不一致均拒绝。省略该参数可以独立打包，但结果明确标为`UNVERIFIED`，不能称为已与普通字体配对。两份输入的来源／许可由调用者负责。

生成的`page_XX.bin`每页0x4000字节：一个小字连续占64字节，四个16字节图块依次为左上、右上、左下、右下，槽偏移为`(gid & 255) * 64`。这与普通字页内的分块排列不同，不能互换。`widths.bin`为0xB00字节，按完整gid索引；未分配项为0，是否分配以`charmap.csv`为准。`blank_page.bin`、各页及字符表的身份记录在清单中；缺页的指针须由后续安装器绑定空白页。

工具不设置ROM地址、不安装代码、不读取现有字库或存档；新目录和输出只含调用者输入生成的字形。它不能替代字体分流、按实际消费者选字库，以及完整生产安装流程。

可选本地mGBA开发库、GNU Arm工具和C编译器时，`python3 -B tools/check_small_font_cpu.py --mgba-prefix /path/to/local-mgba-prefix`会用自绘测试字执行现行小字解码代码，覆盖ROM及RAM中的代码入口、页边界、字宽、回退和损坏图块反例。原生图块解压由独立合成回调替代；这不等于游戏画面或GBARunner3设备验收。

对照原版解码时，两版原生图块例程使用的lookup表地址不同：火红日版Rev0为文件偏移0x1CDF40，叶绿日版Rev0为0x1CDF1C。`glyph_codec.py`的默认偏移是叶绿，使用火红时应传入经本版ROM身份与原生例程确认的`lookup_offset`。两版原版均已只读核对81种合法四像素行及FF空白；这不是实际窗口显示验收。

## ARM7可调用解码核心

shared/patches/cn_glyph.s从项目自有四图块算法整理为参数化接口，去掉旧固定ROM／RAM地址和诊断分支；它不是旧机器码的逐字节导出，不是完整生产钩子的等价替代。

可执行make asm；GNU Arm binutils编译新增的cn_glyph.bin。链接地址0x08F00000只是构建示例，不表示该地址可分配。入口cn_decode_glyph的参数为：

| 输入 | 内容 |
|---|---|
| r0 | 无符号私有glyph ID，调用者从F7＋BE u16中解出 |
| r1 | 下方配置结构的地址，6项对齐u32 |
| config+0 | 连续页指针表的地址；缺失页须填blank_page地址 |
| config+4 | 页表项数，而非最大页号；通常最大页号＋1 |
| config+8 | 完整0x4000字节空白页地址 |
| config+12 | 可写、至少0x80字节的glyph scratch |
| config+16 | 可写、至少2字节的宽／高度量位置 |
| config+20 | 本版原生DecompressGlyphTile的Thumb函数指针 |

读取四个16B源块（页内槽＋0、＋0x10、＋0x100、＋0x110），原生回调分别写scratch＋0、＋0x20、＋0x40、＋0x60，最后设置宽／高12、12。r4～r7和SP恢复；r0～r3／条件码可破坏。调用者和回调都须满足栈、寄存器及内存ABI；调用者负责验证配置、地址、ROM身份、页数和缓冲生命周期，核心不自检所有指针。

只支持这份四图块12×12契约；原版小字／Copy1等其它布局不能擅自接入。非法页号回退blank_page；页内未分配槽由打包器的FF填充提供空白。没有读取或改变昵称、存档及OT/PID记录。

代码限定ARM7TDMI／Thumb1，以显式参数／回调决定用途，不用固定返回地址判断读写。两处链接地址的机器码相同只证明本核心可重定位，不等于完成GBARunner3重映射、游戏窗口或硬件验收。

## 验证边界与下一步

测试含自绘矩阵回解、槽边界、页上限、编码器连接、裁切／重复／格式拒绝和CLI新目录读回。安装GNU Arm binutils时还运行ARM7汇编及两处链接地址比较；没有工具链则明确SKIP，不伪报编译通过。

最初字库／核心批未安装进ROM；后续[首句实验](ORIGINAL_PROBE.md)另有本版限定适配及运行记录。通用字宽／扫描和多字体仍待补，不直接复用历史地址和FF尾部。
