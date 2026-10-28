# 现行中文渲染的所选生产组件

2026-10-27补充：[F7测宽分派及下一层字体入口](WIDTH_SCANNERS.md)和小字测量核心已加入同一工具，火红现在8组件、叶绿7组件。下文四组件是首批核心；新清单还明确提示叶绿R89原生回退地址落入分派表的隐患，不构成完整渲染安全结论。

这一批公开普通字形解码、小字解码、窄标点字宽和各版一个分流入口。它们来自项目自有生产源码，编译后与火红2.3／BUILD0111、叶绿2.3／R89对应区域逐字节一致。**这是部分组件的源码导出，不是完整中文引擎，也不是原版安装器。**

## 编译与只读核对

需要Python≥3.10及GNU Arm binutils，目标ARM7TDMI／Thumb1。无需下载游戏或字体即可编译：

```sh
# 默认仅在内存中生成代码并打印组件清单：
python3 -B tools/renderer_module.py compile --profile firered-2.3-0111
# 也可写到尚不存在的目录，内含组件代码和manifest.json：
mkdir -p build
python3 -B tools/renderer_module.py compile --profile leafgreen-2.3-r89 --output-dir build/lg-render
```

这些代码使用生产版固定链接地址及外部依赖。生成.bin不表示已批准相应ROM窗口可写；不能直接把这些文件放进原版。

对自己持有的精确发布件，可运行只读核对：

```sh
python3 -B tools/renderer_module.py verify --profile firered-2.3-0111 --rom /path/to/local-fr-release.gba
python3 -B tools/renderer_module.py verify --profile leafgreen-2.3-r89 --rom /path/to/local-lg-release.gba
```

只接受以下16MiB身份；不是日版原版的SHA：

| profile | 完整SHA-256 |
|---|---|
| firered-2.3-0111 | 9c92e22573fad9432fe5c64c0c9c810eb504ce73a8660ceff8f7282714b48b6d |
| leafgreen-2.3-r89 | 6012bf84ffbf48f0e88c45e9f04977c7cc79ee781f79184b263d04f247f0ff56 |

verify核对输入身份、RenderText／测宽绑定、所选代码及桥接、普通页表与空白回退页、小字页指针和宽度表范围，并在结束时复核输入未变。输出不含字模或译文。compile不读取游戏；verify没有写出选项。

## 接口和布局

下表是ROM文件偏移，运行地址需加0x08000000；Thumb函数指针最低位为1。

| 组件 | 火红偏移／大小 | 叶绿偏移／大小 |
|---|---|---|
| shared/patches/cn_main_production.s | 0x1DB3CC／244B | 0x1DB3A8／244B |
| shared/patches/cn_small_production.s | 0x9D13E0／108B | 0x9D1400／108B |
| 各版patches/glyph_metrics.s | 0x1DB630／32B | 0x1DB49C／44B |
| 火红intro_font_gate／叶绿storage_font_gate | 0x1DB4C0／76B | 0x6DFB14／160B |
| shared/patches/small_measure_production.s | 0x7B8450／120B | 0x6D5048／120B |

- 普通入口继承RenderText现场：r3是已经消费的字符字节、r6是打印器指针。F7后读取BE u16私有字形ID；非F7保持原生分派返回语义。普通绘制入口在组件+0x22，以r0传ID。保留的模板+4读取是windowId，不能当成fontId。
- 普通字体按页表定位，每字四片源数据偏移为0、16、0x100、0x110；页内槽采用既有bank布局。非法页退到空白页。窄标点回调按源地址决定10／2／12px字宽，正常绘制高度13px。
- 真正的小字解码器以r0传ID、r1=0选择小字；r1非零或ID超界则转普通绘制。每字连续64B，与普通字库布局不同，不能直接复用现有font_pack输出。宽度来自独立0xB00字节表，高度13px；字形本身应预先绘制为小字。
- 两者写入原有0x03003DE0字形scratch和0x03003E60尺寸区，调用原生0x08002F5D图块例程。r4–r7及栈按各自源码保存，不能把这些入口当作任意上下文可调用的通用库。
- 火红所选入口处理新游戏特定文本，其他情况继续到0x087B82A5。叶绿所选入口处理电脑五字名，其他情况继续到0x086DF001。这两个位置的下一层已在10月27日补入，但更后的分流链仍未完整公开；编译匹配不代表所有分流条件已覆盖。

## 还缺什么

共享F7测宽分派、小字测量核心及[自备小字页／宽度表打包接口](FONT_PIPELINE.md#自备小字和普通字编号配对)已补入；小字上下文包装器、剩余字体分流链，以及精确原版的生产安装与资源分配编排仍待整理。小字页表和现用宽度资源只在本地ROM核验，不随源码分发。普通字库也不随仓库提供。

已有cn_glyph.s是独立参数化实验核心，build_original_probe.py是首句限定实验。两者与本页生产组件用途不同，不能拼在一起就宣称完整构建已闭合。

公开测试包含合成审计夹具、可选GNU汇编哈希和新增F7测宽分派CPU检查，均无游戏／字体输入。CPU范围及停止边界见测宽文档；首批绘制组件与字体链没有运行显示验证，没有新增Delta或GBARunner3验收；整套渲染runtime仍保持UNOBSERVED。
