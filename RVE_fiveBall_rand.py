# -*- coding: utf-8 -*-
"""
Abaqus 自动化脚本：复合材料代表性体积单元 (RVE) 稳态热传导仿真
功能：在 80x40x50 mm 基体中随机分布 5 个半径 10 mm 的不重叠铜球。
分析类型：稳态热传导 (Steady-state Heat Transfer)
边界条件：X=0 (100C), X=80 (0C)
"""

from abaqus import *
from abaqusConstants import *
import random
import mesh

# ============================ 1. 几何与分布参数 ============================
LENGTH, WIDTH, HEIGHT = 80.0, 40.0, 50.0  
RADIUS = 10.0                             
NUM_SPHERES = 5                           
X_MIN, X_MAX = 18.0, 62.0                 # 限制球体 X 轴中心，确保不超出左右边界

def create_sphere_part(mdl, part_name, radius):
    """利用旋转法创建球体零件"""
    sketch = mdl.ConstrainedSketch(name='__temp__', sheetSize=radius*4)
    sketch.ConstructionLine(point1=(0.0, -radius), point2=(0.0, radius))
    sketch.ArcByCenterEnds(center=(0.0, 0.0), point1=(0.0, radius), point2=(0.0, -radius))
    sketch.Line(point1=(0.0, radius), point2=(0.0, -radius))
    p = mdl.Part(name=part_name, dimensionality=THREE_D, type=DEFORMABLE_BODY)
    p.BaseSolidRevolve(sketch=sketch, angle=360.0)

# 初始化模型数据库
Mdb()
model = mdb.Model(name='RVE_HeatTransfer')

# ============================ 2. 创建几何零件 ============================
# 创建基体
matrix_sketch = model.ConstrainedSketch(name='Matrix_Sketch', sheetSize=200.0)
matrix_sketch.rectangle(point1=(0.0, 0.0), point2=(LENGTH, WIDTH))
model.Part(name='Matrix_Part', dimensionality=THREE_D, type=DEFORMABLE_BODY)
p_matrix = model.parts['Matrix_Part']
p_matrix.BaseSolidExtrude(sketch=matrix_sketch, depth=HEIGHT)

# 创建球体夹杂
for i in range(NUM_SPHERES):
    create_sphere_part(model, f'Sphere_{i+1}', RADIUS)

# ============================ 3. 定义材料属性与网格 ============================
model.Material(name='Resin_Mat').Conductivity(table=((0.00027, ), )) # W/mm*K
model.Material(name='Cu_Mat').Conductivity(table=((0.4, ), ))
model.HomogeneousSolidSection(name='Resin_Sec', material='Resin_Mat')
model.HomogeneousSolidSection(name='Cu_Sec', material='Cu_Mat')

# 基体网格 (DC3D8 热传导单元)
p_matrix.SectionAssignment(region=(p_matrix.cells,), sectionName='Resin_Sec')
p_matrix.seedPart(size=2.0) 
p_matrix.setElementType(regions=(p_matrix.cells,), elemTypes=(mesh.ElemType(elemCode=DC3D8),))
p_matrix.generateMesh()

# 球体网格 (DC3D4 四面体单元)
for i in range(NUM_SPHERES):
    p_sphere = model.parts[f'Sphere_{i+1}']
    p_sphere.SectionAssignment(region=(p_sphere.cells,), sectionName='Cu_Sec')
    p_sphere.seedPart(size=2.0)
    p_sphere.setElementType(regions=(p_sphere.cells,), elemTypes=(mesh.ElemType(elemCode=DC3D4),))
    p_sphere.generateMesh()

# ============================ 4. 组装与随机放置 ============================
asm = model.rootAssembly
asm.DatumCsysByDefault(CARTESIAN)
m_inst = asm.Instance(name='Matrix_Inst', part=p_matrix, dependent=ON)

sphere_inst_names = []
sphere_centers = []
random.seed()
count = 0
while count < NUM_SPHERES:
    x = random.uniform(X_MIN, X_MAX)
    y = random.uniform(RADIUS, WIDTH - RADIUS)
    z = random.uniform(RADIUS, HEIGHT - RADIUS)
    
    # 防重叠检查
    overlap = any(((x-cx)**2 + (y-cy)**2 + (z-cz)**2)**0.5 < 2.05*RADIUS for (cx, cy, cz) in sphere_centers)
    
    if not overlap:
        sphere_centers.append((x, y, z))
        s_name = f'Sphere_Inst_{count+1}'
        asm.Instance(name=s_name, part=model.parts[f'Sphere_{count+1}'], dependent=ON)
        asm.translate(instanceList=(s_name,), vector=(x, y, z))
        sphere_inst_names.append(s_name)
        count += 1

# ============================ 5. 约束与边界条件 ============================
# 设置嵌入约束 (Embedded Region)
sphere_cells = asm.instances[sphere_inst_names[0]].cells
for name in sphere_inst_names[1:]:
    sphere_cells += asm.instances[name].cells

model.EmbeddedRegion(name='Embed_Constraint', 
    embeddedRegion=asm.Set(name='Inclusions', cells=sphere_cells), 
    hostRegion=asm.Set(name='Host', cells=m_inst.cells))

# 热传导分析步
model.HeatTransferStep(name='Steady_Thermal', previous='Initial', response=STEADY_STATE)

# 施加温度边界 (X=0 为 100C, X=80 为 0C)
f_hot = m_inst.faces.findAt(((0.0, WIDTH/2, HEIGHT/2),))
f_cold = m_inst.faces.findAt(((LENGTH, WIDTH/2, HEIGHT/2),))
model.TemperatureBC(name='Hot_Side', createStepName='Steady_Thermal', 
    region=asm.Set(faces=f_hot, name='Set_Hot'), magnitude=100.0)
model.TemperatureBC(name='Cold_Side', createStepName='Steady_Thermal', 
    region=asm.Set(faces=f_cold, name='Set_Cold'), magnitude=0.0)

# ============================ 6. 创建作业 ============================
mdb.Job(name='Thermal_RVE_Final', model='RVE_HeatTransfer')

print("-" * 30)
print("✅ 模型生成完毕！[Thermal_RVE_Final]")
print("已应用 100C - 0C 温差边界条件。")
print("-" * 30)