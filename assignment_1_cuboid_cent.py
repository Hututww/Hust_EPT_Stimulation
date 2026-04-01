# -*- coding: utf-8 -*-
"""
Abaqus 自动化脚本：中心长方体嵌入式导热仿真
1. 基体：80(X) x 50(Y) x 40(Z) 实心长方体。
2. 铜块：20(X) x 10(Y) x 10(Z) 中心长方体。
3. 约束：Embedded Region (嵌入式约束)。
4. 网格：全六面体 Hex (DC3D8)，基体 2.0，铜块 1.0。
"""

from abaqus import *
from abaqusConstants import *
import mesh

# ============================ 1. 参数定义 ============================
# 基体 (Matrix)
L, W, H = 80.0, 50.0, 40.0  
# 铜块 (Inclusion)
l_inc, w_inc, h_inc = 20.0, 10.0, 10.0  

MESH_SIZE_MATRIX = 7
MESH_SIZE_INC = 6

# ============================ 2. 建模 ============================
Mdb()
model = mdb.Model(name='Rect_Inclusion_Model')

# --- 创建基体 Part ---
s1 = model.ConstrainedSketch(name='Matrix_Sketch', sheetSize=200.0)
s1.rectangle(point1=(0.0, 0.0), point2=(L, W))
p_matrix = model.Part(name='Matrix_Solid', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p_matrix.BaseSolidExtrude(sketch=s1, depth=H)

# --- 创建铜块 Part ---
s2 = model.ConstrainedSketch(name='Inc_Sketch', sheetSize=100.0)
s2.rectangle(point1=(0.0, 0.0), point2=(l_inc, w_inc))
p_inc = model.Part(name='Inclusion_Solid', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p_inc.BaseSolidExtrude(sketch=s2, depth=h_inc)

# ============================ 3. 属性指派 ============================
model.Material(name='Resin').Conductivity(table=((0.00027, ), ))
model.Material(name='Copper').Conductivity(table=((0.4, ), ))
model.HomogeneousSolidSection(name='Resin_Sec', material='Resin')
model.HomogeneousSolidSection(name='Copper_Sec', material='Copper')

p_matrix.SectionAssignment(region=(p_matrix.cells,), sectionName='Resin_Sec')
p_inc.SectionAssignment(region=(p_inc.cells,), sectionName='Copper_Sec')

# ============================ 4. 网格划分 (全六面体) ============================
# 基体网格
p_matrix.setMeshControls(regions=p_matrix.cells, technique=SWEEP, elemShape=HEX)
p_matrix.seedPart(size=MESH_SIZE_MATRIX)
p_matrix.setElementType(regions=(p_matrix.cells,), elemTypes=(mesh.ElemType(elemCode=DC3D8),))
p_matrix.generateMesh()

# 铜块网格 (由于是长方体，Hex 极其稳定)
p_inc.setMeshControls(regions=p_inc.cells, technique=SWEEP, elemShape=HEX)
p_inc.seedPart(size=MESH_SIZE_INC)
p_inc.setElementType(regions=(p_inc.cells,), elemTypes=(mesh.ElemType(elemCode=DC3D8),))
p_inc.generateMesh()

# ============================ 5. 组装与嵌入 ============================
asm = model.rootAssembly
asm.DatumCsysByDefault(CARTESIAN)
m_inst = asm.Instance(name='Matrix_Inst', part=p_matrix, dependent=ON)
i_inst = asm.Instance(name='Inc_Inst', part=p_inc, dependent=ON)

# 将铜块移动到几何中心
# 铜块初始在 (0,0,0)-(20,10,10)，需要平移到中心点 (40, 25, 20)
# 平移矢量 = (L/2 - l_inc/2, W/2 - w_inc/2, H/2 - h_inc/2)
asm.translate(instanceList=('Inc_Inst',), 
              vector=(L/2.0 - l_inc/2.0, W/2.0 - w_inc/2.0, H/2.0 - h_inc/2.0))

# 建立嵌入约束
model.EmbeddedRegion(name='Embed_Inclusion', 
    embeddedRegion=asm.Set(name='Inc_Set', cells=i_inst.cells), 
    hostRegion=asm.Set(name='Matrix_Set', cells=m_inst.cells))

# ============================ 6. 分析步与边界条件 ============================
model.HeatTransferStep(name='Steady_Thermal', previous='Initial', response=STEADY_STATE)

# X=0 热端 100C
f1 = m_inst.faces.findAt(((0.0, W/2, H/2),))
asm.Set(faces=f1, name='Set_Hot')
model.TemperatureBC(name='Hot_BC', createStepName='Steady_Thermal', 
    region=asm.sets['Set_Hot'], magnitude=100.0)

# X=80 冷端 0C
f2 = m_inst.faces.findAt(((L, W/2, H/2),))
asm.Set(faces=f2, name='Set_Cold')
model.TemperatureBC(name='Cold_BC', createStepName='Steady_Thermal', 
    region=asm.sets['Set_Cold'], magnitude=0.0)

# ============================ 7. Job ============================
job_name = 'Rect_Inclusion_RVE_Job'
if job_name in mdb.jobs.keys(): del mdb.jobs[job_name]
mdb.Job(name=job_name, model='Rect_Inclusion_Model').submit()

print("-" * 50)
print("🚀 中心长方体模型已提交！")
print(f"基体: {L}x{W}x{H}, 铜块: {l_inc}x{w_inc}x{h_inc}")
print("网格类型: 100% 六面体 (DC3D8)")
print("-" * 50)