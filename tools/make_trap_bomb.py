"""Build Dragan's bomb-trap Blueprint: a clone of the bear-trap actor BP_ENV_co_TrapDamage that shows the Explosives
model instead of the bear trap and explodes with the Explosives' effects. Research pass item 3 (ROADMAP.md).

    python tools/make_trap_bomb.py            -> mods/dragan_trap/src/BP_ENV_co_TrapBomb_N105P.json (+ .uasset/.uexp via UAssetGUI)

Edits on the UAssetGUI JSON of the vanilla Blueprint (re/assets/BP_ENV_co_TrapDamage.json):
  1. rename package/class/functions BP_ENV_co_TrapDamage -> BP_ENV_co_TrapBomb_N105P (in place, so name indices hold);
  2. activation particle P_EFF_BoobyTrap002 (P009) -> P_EFF_Bomb001 (the Explosives' blast); sound -> SE_GIM_BOMB_EXPLODE;
     placement particle 001 stays vanilla (Test 28);
  3. both bear-trap mesh templates get RelativeScale3D 0.001 (invisible; the graph still plays them and signals the end);
  4. new StaticMeshComponent template showing SM_ENV_co_Bomb000 (the Explosives model, copied from BP_ENV_co_Bomb000)
     plus its SCS node under DefaultSceneRoot, with collision profile NoCollision (Test 28 crash);
  5. the Explosives' lit-fuse spark P_EFF_BombSpark as a second new component (Test 28b).
Structure read from BP_ENV_co_Bomb000 (docs/MECHANICS.md, ROADMAP.md). Untested in game.
"""
import copy, json, os, subprocess, sys, uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 're', 'assets', 'BP_ENV_co_TrapDamage.json')
OUTDIR = os.path.join(ROOT, 'mods', 'dragan_trap', 'src')
NEW = 'BP_ENV_co_TrapBomb_N105P'
UAG = os.path.join(ROOT, 'tools', 'uassetgui', 'UAssetGUI.exe')


def main():
    txt = open(SRC, encoding='utf-8').read()
    txt = txt.replace('BP_ENV_co_TrapDamage', NEW)
    # 001 is the placement effect (AddComponent-0 in the spawn branch), 002 the activation effect (with the snap sound).
    # Test 28: swapping 001 too played the blast on placement, so only 002 is swapped.
    txt = txt.replace('/Game/Newera/Effect/Particle/ability/P009/P_EFF_BoobyTrap002', '/Game/Newera/Effect/Particle/common/P_EFF_Bomb001')
    txt = txt.replace('P_EFF_BoobyTrap002', 'P_EFF_Bomb001')
    txt = txt.replace('SE_BTL_ABL_P009_BOOBY_TRAP_CAST02', 'SE_GIM_BOMB_EXPLODE')
    j = json.loads(txt)
    E, I, N = j['Exports'], j['Imports'], j['NameMap']

    def name(n):
        if n not in N: N.append(n)

    def exp(objname):
        return [k for k, e in enumerate(E) if e['ObjectName'] == objname][0]

    def imp(d):
        I.append(dict({'$type': 'UAssetAPI.Import, UAssetAPI', 'PackageName': None, 'bImportOptional': False}, **d))
        name(d['ObjectName']); name(d['ClassPackage']); name(d['ClassName'])
        return -len(I)

    pkg_engine = -([k for k, im in enumerate(I) if im['ObjectName'] == '/Script/Engine'][0] + 1)
    cls_smc = imp({'ObjectName': 'StaticMeshComponent', 'OuterIndex': pkg_engine, 'ClassPackage': '/Script/CoreUObject', 'ClassName': 'Class'})
    pkg_mesh = imp({'ObjectName': '/Game/Newera/Environment/Common/Model/SM_ENV_co_Bomb000', 'OuterIndex': 0, 'ClassPackage': '/Script/CoreUObject', 'ClassName': 'Package'})
    mesh = imp({'ObjectName': 'SM_ENV_co_Bomb000', 'OuterIndex': pkg_mesh, 'ClassPackage': '/Script/Engine', 'ClassName': 'StaticMesh'})
    dflt = imp({'ObjectName': 'Default__StaticMeshComponent', 'OuterIndex': pkg_engine, 'ClassPackage': '/Script/Engine', 'ClassName': 'StaticMeshComponent'})

    cls_export = exp(NEW + '_C') + 1          # FPackageIndex of the class export
    scs = exp('SimpleConstructionScript_0')
    root_node = exp('SCS_Node_0')

    # 3. shrink the bear-trap meshes: copy a vector struct (RelativeLocation from the Bomb000 template) as RelativeScale3D
    bomb = json.load(open(os.path.join(ROOT, 're', 'assets', 'BP_ENV_co_Bomb000.json'), encoding='utf-8'))
    btmpl = [e for e in bomb['Exports'] if e['ObjectName'] == 'SM_ENV_co_Bomb000_GEN_VARIABLE'][0]
    vec = [p for p in btmpl['Data'] if p['Name'] == 'RelativeLocation'][0]
    scale = copy.deepcopy(vec); scale['Name'] = 'RelativeScale3D'; scale['Value'][0]['Name'] = 'RelativeScale3D'
    scale['Value'][0]['Value'].update({'X': 0.001, 'Y': 0.001, 'Z': 0.001})
    name('RelativeScale3D'); name('Vector')
    for t in ('SM_ENV_co_BearTrap000_GEN_VARIABLE', 'SM_ENV_co_BearTrap001_DM_GEN_VARIABLE'):
        E[exp(t)]['Data'].append(copy.deepcopy(scale))

    # 4a. StaticMeshComponent template (copy of the Explosives' one, re-indexed)
    t = copy.deepcopy(btmpl)
    t.update({'OuterIndex': cls_export, 'ClassIndex': cls_smc, 'TemplateIndex': dflt,
              'SerializationBeforeSerializationDependencies': [cls_export], 'CreateBeforeSerializationDependencies': [mesh],
              'SerializationBeforeCreateDependencies': [cls_smc, dflt], 'CreateBeforeCreateDependencies': [cls_export]})
    for p in t['Data']:
        if p['Name'] == 'StaticMesh': p['Value'] = mesh
    # Test 28 crash: the Explosives mesh kept its default (block-all) collision, blocking walking units and projectile
    # arcs. The bear-trap mesh ignores Pawn. Give ours a BodyInstance with the engine's NoCollision profile.
    bi = copy.deepcopy([p for p in E[exp('SM_ENV_co_BearTrap001_DM_GEN_VARIABLE')]['Data'] if p['Name'] == 'BodyInstance'][0])
    bi['Value'] = [v for v in bi['Value'] if v['Name'] == 'CollisionProfileName']
    bi['Value'][0]['Value'] = 'NoCollision'
    name('NoCollision'); name('BodyInstance'); name('CollisionProfileName')
    t['Data'].append(bi)
    for n in ('SM_ENV_co_Bomb000_GEN_VARIABLE', 'StaticMesh', 'bReceivesDecals', 'RelativeLocation'): name(n)
    E.append(t); tmpl_idx = len(E)

    # 4b. its SCS node (copy of the trap's SCS_Node_2, re-pointed)
    node = copy.deepcopy(E[exp('SCS_Node_2')])
    node['ObjectName'] = 'SCS_Node_3'; name('SCS_Node_3'); name('SM_ENV_co_Bomb000')
    node['CreateBeforeSerializationDependencies'] = [tmpl_idx, cls_smc]
    for p in node['Data']:
        if p['Name'] == 'ComponentClass': p['Value'] = cls_smc
        elif p['Name'] == 'ComponentTemplate': p['Value'] = tmpl_idx
        elif p['Name'] == 'VariableGuid': p['Value'][0]['Value'] = '{' + str(uuid.uuid4()).upper() + '}'
        elif p['Name'] == 'InternalVariableName': p['Value'] = 'SM_ENV_co_Bomb000'
    E.append(node); node_idx = len(E)

    # 4c. lit fuse (Test 28b, user): the Explosives' own spark component P_EFF_BombSpark, copied with its offset (it sits
    # beside the mesh under a Scene at the origin in BP_ENV_co_Bomb000). Its 'start with tick disabled' override is dropped
    # so the particle runs from spawn (the Explosives' graph drives it; ours doesn't).
    cls_psc = -([k for k, im in enumerate(I) if im['ObjectName'] == 'ParticleSystemComponent' and im['ClassName'] == 'Class'][0] + 1)
    dflt_psc = -([k for k, im in enumerate(I) if im['ObjectName'] == 'Default__ParticleSystemComponent'][0] + 1)
    pkg_spark = imp({'ObjectName': '/Game/Newera/Effect/Particle/environment/P_EFF_BombSpark', 'OuterIndex': 0, 'ClassPackage': '/Script/CoreUObject', 'ClassName': 'Package'})
    spark = imp({'ObjectName': 'P_EFF_BombSpark', 'OuterIndex': pkg_spark, 'ClassPackage': '/Script/Engine', 'ClassName': 'ParticleSystem'})
    stmpl = copy.deepcopy([e for e in bomb['Exports'] if e['ObjectName'] == 'P_EFF_BombSpark_GEN_VARIABLE'][0])
    stmpl.update({'OuterIndex': cls_export, 'ClassIndex': cls_psc, 'TemplateIndex': dflt_psc,
                  'SerializationBeforeSerializationDependencies': [cls_export], 'CreateBeforeSerializationDependencies': [spark],
                  'SerializationBeforeCreateDependencies': [cls_psc, dflt_psc], 'CreateBeforeCreateDependencies': [cls_export]})
    stmpl['Data'] = [q for q in stmpl['Data'] if q['Name'] != 'PrimaryComponentTick']
    for q in stmpl['Data']:
        if q['Name'] == 'Template': q['Value'] = spark
    for n in ('P_EFF_BombSpark_GEN_VARIABLE', 'Template', 'RelativeLocation', 'Vector'): name(n)
    E.append(stmpl); stmpl_idx = len(E)
    snode = copy.deepcopy(E[exp('SCS_Node_2')])
    snode['ObjectName'] = 'SCS_Node_4'; name('SCS_Node_4'); name('P_EFF_BombSpark')
    snode['CreateBeforeSerializationDependencies'] = [stmpl_idx, cls_psc]
    for q in snode['Data']:
        if q['Name'] == 'ComponentClass': q['Value'] = cls_psc
        elif q['Name'] == 'ComponentTemplate': q['Value'] = stmpl_idx
        elif q['Name'] == 'VariableGuid': q['Value'][0]['Value'] = '{' + str(uuid.uuid4()).upper() + '}'
        elif q['Name'] == 'InternalVariableName': q['Value'] = 'P_EFF_BombSpark'
    E.append(snode); snode_idx = len(E)

    def add_obj(arr_prop, value):
        item = copy.deepcopy(arr_prop['Value'][0]); item['Name'] = str(len(arr_prop['Value'])); item['Value'] = value
        arr_prop['Value'].append(item)

    add_obj([p for p in E[scs]['Data'] if p['Name'] == 'AllNodes'][0], node_idx)
    add_obj([p for p in E[root_node]['Data'] if p['Name'] == 'ChildNodes'][0], node_idx)
    E[scs]['CreateBeforeSerializationDependencies'] = E[scs].get('CreateBeforeSerializationDependencies', []) + [node_idx]
    E[root_node]['CreateBeforeSerializationDependencies'] = E[root_node].get('CreateBeforeSerializationDependencies', []) + [node_idx]
    add_obj([p for p in E[scs]['Data'] if p['Name'] == 'AllNodes'][0], snode_idx)
    add_obj([p for p in E[root_node]['Data'] if p['Name'] == 'ChildNodes'][0], snode_idx)
    E[scs]['CreateBeforeSerializationDependencies'] += [snode_idx]
    E[root_node]['CreateBeforeSerializationDependencies'] += [snode_idx]

    if isinstance(j.get('DependsMap'), list):
        while len(j['DependsMap']) < len(E): j['DependsMap'].append([])
    for g in j.get('Generations') or []:
        g['ExportCount'] = len(E); g['NameCount'] = len(N)

    os.makedirs(OUTDIR, exist_ok=True)
    out = os.path.join(OUTDIR, NEW + '.json')
    json.dump(j, open(out, 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
    print(f'wrote {out}: {len(E)} exports, {len(I)} imports, {len(N)} names; template {tmpl_idx}, node {node_idx}')
    asset = os.path.join(OUTDIR, 'out', 'Environment', 'Common', 'BluePrint', NEW + '.uasset')
    os.makedirs(os.path.dirname(asset), exist_ok=True)
    env = dict(os.environ, DOTNET_ROLL_FORWARD='Major')
    r = subprocess.run([UAG, 'fromjson', out, asset], env=env, capture_output=True, text=True, timeout=300)
    print('fromjson', r.returncode, (r.stdout + r.stderr).strip()[:400], os.path.exists(asset))


if __name__ == '__main__':
    main()
