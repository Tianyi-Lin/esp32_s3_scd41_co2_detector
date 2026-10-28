# 模型生成与检查源码

这里归档了本地建模工作区中与 ESP32-S3 / SCD41 外壳相关的 Python 脚本及 FreeCAD 宏。生成脚本、辅助模块、历史修补和检查脚本保留原文件名和代码；无关的毕业实验绘图、网络测试绘图脚本没有收录。

## 主要入口

| 文件 | 用途 |
| --- | --- |
| `design_inverted_scd41_cover.py` | 最新倒装后盖预览：传感器朝外、表面内缩约 1 mm，导出独立后盖及倒装装配。方案尚未定稿。 |
| `redesign_bottom_sensor_landscape.py` | 未倒装的横置后盖：长边平行外壳长边，安装孔距 X20 / Y18。 |
| `create_compact_stacked_enclosure.py` | 紧凑双层外壳的整机生成入口，调用本目录多个几何辅助模块。 |
| `rebuild_editable_enclosure.py` | 将实体重建成参数化零件。 |
| `rebuild_direct_sketch_enclosure.py` | 生成带草图和特征历史的独立编辑工程；依赖上一个模块。 |
| `repair_sketch_engineering.py`、`repair_top_native_fillet.py` | 草图孔位联动修正及上盖圆角修复。 |
| `create_exploded_inspection.py` | 爆炸检查工程。 |
| `create_five_color_inspection.FCMacro` | 五色半透明装配检查宏，需要 FreeCAD 图形界面。 |
| `export_checked_enclosure_steps.py`、`audit_print_mesh_orientation.py` | STEP 导出和打印网格检查。 |

其余 `apply_*`、`resize_*`、`update_*` 等包含历史阶段的几何修改；`inspect_*`、`audit_*`、`test_*`、`probe_*` 等记录检查或试验。文件名前缀不保证只读，应先看代码中的保存、导出语句。

## 运行前必读

1. 这些是**原始工作源码快照**，不是一个可直接“一键顺序运行所有文件”的发布工具包。上传时只验证了语法和源码同步，没有重新执行建模，也没有重新验证所有历史脚本。
2. 许多脚本保留原机器的绝对路径，包括模型目录、`sys.path` 和 `.cad-recovery` 输出目录。在其他位置运行前，必须核对并修改对应路径；不要只修改一个入口却忽略其导入模块。
3. 部分脚本在导入或执行时会创建工程、修改已有文件或保存导出。**先复制模型到独立测试目录，再运行**；不要直接针对唯一的模型原件执行，也不要把历史修补脚本重复应用到最新零件。
4. 几何脚本依赖 FreeCAD 自带 Python 模块，如 `FreeCAD`、`Part`、`Sketcher`、`Mesh`、`MeshPart`；普通系统 Python 通常不能直接运行。带 `FreeCADGui` 的脚本需要图形界面。部分检查还依赖 NumPy 等模块。
5. 本次建模使用 FreeCAD 26.3.0 RC2。主生成脚本不代表所有历史脚本都经过此版本的独立回归测试。
6. 最新倒装预览依赖横置装配以及草图重建辅助模块；生成后仍需解决整机厚度和实际接线插头空间问题，不能据此直接认定可打印装配。

脚本与已保存模型共同归档，但并非每个历史脚本都对应当前发布的几何状态。已有 `.FCStd` 才是本次同步的模型快照；手工改尺寸时可直接使用带草图特征的工程。
