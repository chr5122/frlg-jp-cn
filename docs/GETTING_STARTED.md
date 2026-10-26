# 开始使用

## 先选你要做的事

- **了解／开发工具**：本页的测试和小示例无需游戏文件，适合作为第一次贡献。
- **检查自己持有的ROM身份**：使用inspect_rom，只读；已有SHA记录不是ROM下载入口。
- **直接修改日版原版**：使用[patch_rom](EDIT_ORIGINAL.md)和自己审核过的字节清单；支持火红／叶绿Rev0，默认内存校验，按需写出新文件，不依赖历史汉化父版。当前没有完整汉化清单。
- **准备自己有权使用的中文字形**：使用[字库打包流程](FONT_PIPELINE.md)输出页和编码字表；不需ROM或历史供体，但这一步本身不会给原版安装中文引擎。
- **生成局部汇编载荷或历史增量**：先看[依赖表](DEPENDENCIES.md)和[构建说明](BUILDING.md)。必须提供工具要求的精确输入；不能套到未知ROM。
- **从原版构建当前完整汉化**：暂不支持。[路线图](ROADMAP.md)明确列出缺失项，不要运行一串旧FIX命令尝试拼出当前版。

## 环境和测试

需要Python 3.10或更新版本、Git。纯Python工具只用标准库；不需要pip、模拟器、字体、ROM或存档。

```sh
git clone https://github.com/chr5122/frlg-jp-cn.git
cd frlg-jp-cn
python3 -B tools/check.py
```

Windows通常将python3替换为python。此入口不依赖make；从其它目录运行时可传入脚本绝对路径。它先执行合成测试，成功后检查公开文件白名单、二进制和私人信息。任何一步失败都会返回非零，不执行后续发布动作。

Linux／macOS等有make的环境也可执行make check，两者调用同一检查入口。CI测试Python3.10／3.12／3.13；不意味着所有操作系统或设备都经过验证。

## 第一个无素材示例

下面仅解析人工构造的控制符，不含游戏正文。显式选择CN模式：

```sh
python3 -c "import sys; sys.path.insert(0, 'shared'); from frlg.text import exact; s = exact(bytes.fromhex('fd01feff'), 'cn'); print(s.status); print([(kind, raw.hex()) for _, kind, raw in s.tokens])"
```

预期先输出OK，再依次出现parameter(fd01)、layout(fe)、end(ff)。这里验证token结构，不负责运行游戏或判断翻译质量。更多合成用例见tests/。

## 只读检查本地文件

```sh
python3 -B tools/inspect_rom.py --manifest firered/baseline.json --kind release --rom /path/to/local.gba
```

baseline.json记录的是该批公开源码所验证的历史快照，不会自动跟随游戏新版本。身份不匹配时应核对适用版本，不要修改预期SHA绕过门禁。不要把本地文件复制进仓库或issue。

## 第一次贡献

1. Fork仓库并建立用途明确的分支。
2. 做小范围改动，补充能复现旧错误的合成测试。
3. 运行python3 -B tools/check.py，再检查git diff --check和实际差异。
4. 提交PR，说明适用版本、验证结果及没测到的范围。

新公开文件必须逐个加入tools/check_publication.py的白名单，并核清许可／来源；不是取消白名单。报告问题使用issue模板，提交源码使用PR模板。不要上传ROM、译文包、字库或存档。详见[贡献约定](../CONTRIBUTING.md)。
