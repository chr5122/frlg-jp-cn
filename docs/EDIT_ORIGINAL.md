# 直接修改自己的日版原版ROM

目标流程是：**正确日版原版＋自己审核过的修改清单→新ROM**。不要求取得项目历史汉化父版，也不用逐个重放旧FIX。

目前提供的是通用的定点字节修改入口，**不是当前完整汉化的一键构建器**。它不会自动找文本、生成译文、装载中文渲染器或分配空闲地址。已公开的历史增量不能改个输入SHA就当作原版补丁用。

## 支持的输入

仅支持下面两枚16MiB原版，输入按整枚SHA-256核对，不靠文件名或游戏代号猜测：

| 清单中的game | 输入SHA-256 |
|---|---|
| firered-jp-rev0 | `1e4af44b0c75cc8649bfb8649dc4ae5850bf5358bd6b9cd0bf779c99f9db1486` |
| leafgreen-jp-rev0 | `2957b392dc09fc8df45a660af5493368d7bd378d299862f4cc115998e9da0bf2` |

其它修订、美版、中文版、加头或已修改文件均拒绝。请自行合法取得原版，不要上传到仓库或issue。

## 使用修改清单

需要Python≥3.10，无第三方Python依赖。从仓库根目录运行：

```sh
# 默认只在内存校验，不写ROM。
python3 -B tools/patch_rom.py --original /path/to/original.gba --recipe /path/to/recipe.json

# 通过后写入新文件；已有文件、输入原件和清单均不得覆盖。
python3 -B tools/patch_rom.py --original /path/to/original.gba --recipe /path/to/recipe.json --output /path/to/new.gba
```

工具按顺序检查原版身份、清单格式、每处原字节、边界、重叠、保护范围、最终整枚SHA，再选择是否写出新文件；写出后重读校验，并再次核对输入未变。失败退出非零。写盘／重读失败时新文件可能已存在，不能当作验证通过的产物使用。

## 清单格式

以下是**不可直接运行的结构模板**，不是游戏补丁，也不是已核实的地址；不要照抄地址和测试字节到真实ROM。所有offset/start/end均为文件偏移，不是0x08开头的CPU地址。

```json
{
  "schema": 1,
  "game": "firered-jp-rev0",
  "output_sha256": "替换为该方案预先核实的64位小写SHA-256",
  "writes": [
    {"offset": "0x0", "before_hex": "00", "after_hex": "01", "purpose": "patch"}
  ],
  "protected": []
}
```

- 作者应先在本地设计、验证修改，再填写固定的输出SHA；工具故意不提供“忽略哈希”选项。清单内容须与其声称的游戏对应，火红与叶绿不共享地址假设。
- writes必须非空。before_hex/after_hex均为非空等长十六进制串，不扩展ROM，不允许重叠写入。
- purpose可选patch或new_pool；new_pool另外要求原范围全部为FF。**FF不代表已获得资源使用权或已确认可用**，必须结合对应工程资源台账。
- protected必须显式存在。每项为`{"start":"0x100","end":"0x200","name":"自定义保护窗"}`，区间左闭右开，禁止任何写入跨入。空列表不等于项目不存在保护区；本工具不内置完整工程台账。
- 重复JSON字段、未知字段、未知游戏、错误输入／输出SHA、错误原字节、无实际变化均拒绝。

作者可使用shared/frlg/rom.py和text.py等现有模块准备／检查修改，不能把原生JP文本直接换成私有F7中文字节就宣称已汉化；没有配套渲染器和字库，原版不会正确显示。代码、文字参数、结束符、缓冲、指针、资源窗口及设备兼容性仍需分别验证。

## 当前可独立运行的原版研究示例

已有叶绿自绘单字实验无需汉化父版、外部字库或译文：

```sh
python3 -B leafgreen/experiments/first_glyph.py --original /path/to/leafgreen-jp-rev0.gba
```

它在内存中替换一个原生字模槽并验证反解；加--output才写新文件。它会影响该槽原先的字符，**仅用于理解字模，不是可游玩汉化**，也不是把全部日文变中文的功能。通用修改清单的合成范例见tests/test_patching.py，不依赖真实ROM。

## 通过代表什么

PASS只表示固定输入、修改范围和结果字节符合清单，不代表指针用途正确、中文显示正确或游戏流程／Delta／GBARunner3通过。报告固定保留runtime=UNOBSERVED和complete_translation=false，不能把字节门禁当作实机验收。

后续按成熟功能补入真正适用于原版的渲染、名称与菜单适配模块及已授权资源接口；每个功能都应有清晰输入和独立验证，不再要求普通使用者寻找历史父版。
