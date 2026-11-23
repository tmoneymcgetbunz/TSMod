-- [TSMod] ms19_x45_battle_02_old without its missing scene require (mods/cut_battles/make_lua.py).
require("Src/Newera_Handling/Scenario/CommonDef/CharIdDef")
require("Src/Newera_Handling/Scenario/CommonDef/BattleUnitParamId")
require("Src/Newera_Handling/Scenario/CommonDef/ClassBattleBase")
require("Src/Newera_Handling/Scenario/CommonDef/ClassBattlePreparation")
function DEATH_N206()
end
g_TriggerHPZeroTable = {
  {"N206", DEATH_N206}
}
SETTING_VALUES = {
  MapCfgGopId = "BATTLE_MAPCFG_MS19_X45",
  CameraEffectCoordinateStart = {X = 20, Y = 10},
  CameraEffectCoordinateEnd = {X = 10, Y = 10},
  CameraEffectRotationStart = {
    Pitch = 24,
    Yaw = 135,
    Roll = 0
  },
  CameraEffectRotationEnd = {
    Pitch = 24,
    Yaw = 135,
    Roll = 0
  },
  CameraRotationOnPreStart = {
    Pitch = 24,
    Yaw = 135,
    Roll = 0
  },
  InitialBGM = "BGM_PP_140",
  BattleFieldTextId = "TEXT_COMMON_BATTLE_UI_BATTLE_NAME_19_45",
  VictoryRequirementText = "TEXT_COMMON_BATTLE_UI_VICTORY_CONDITION_19_45",
  PostResultTransitionTarget = "/Game/Newera/Map/System/Title_PrePro",
  bUseResultBGM = true,
  ResultBGM = "BGM_M41_ADV_WIN"
}
BattleTemplateInstance:OverrideSetting(SETTING_VALUES)
local wlv = 9

function ClassBattleBase:DebugChangeUnitMasterParameters_Implementation()
  SetupTestPlayUnits(45)
  SetupTestPlayItems(45)
end

function ClassBattle:SetupInitialPositionAndUnit_Implementation()
  AddInitialPosition(15, 12, CHAR_DIR_SOUTH)
  AddInitialPosition(16, 12, CHAR_DIR_SOUTH)
  AddInitialPosition(17, 12, CHAR_DIR_SOUTH)
  AddInitialPosition(18, 12, CHAR_DIR_SOUTH)
  AddInitialPosition(15, 13, CHAR_DIR_SOUTH)
  AddInitialPosition(16, 13, CHAR_DIR_SOUTH)
  AddInitialPosition(17, 13, CHAR_DIR_SOUTH)
  AddInitialPosition(18, 13, CHAR_DIR_SOUTH)
  AddInitialPosition(16, 14, CHAR_DIR_SOUTH)
  AddInitialPosition(17, 14, CHAR_DIR_SOUTH)
  if IsDebugSwitch(DBG_ACTION_FLAG_ENABLE_DEBUG_UNIT_SETTING) == true then
    local initailUnitTable_debug = {
      {
        ID = "UNIT_MASTER_CH_P002",
        X = 16,
        Y = 12
      },
      {
        ID = "UNIT_MASTER_CH_P003",
        X = 17,
        Y = 12
      },
      {
        ID = "UNIT_MASTER_CH_P004",
        X = 18,
        Y = 12
      },
      {
        ID = "UNIT_MASTER_CH_P005",
        X = 15,
        Y = 13
      },
      {
        ID = "UNIT_MASTER_CH_P006",
        X = 16,
        Y = 13
      },
      {
        ID = "UNIT_MASTER_CH_P007",
        X = 17,
        Y = 13
      },
      {
        ID = "UNIT_MASTER_CH_P008",
        X = 18,
        Y = 13
      },
      {
        ID = "UNIT_MASTER_CH_P013",
        X = 16,
        Y = 14
      },
      {
        ID = "UNIT_MASTER_CH_P010",
        X = 17,
        Y = 14
      }
    }
    AddEnforceMissionUnits(initailUnitTable_debug)
  end
  local initailUnitTable = {
    {
      ID = "UNIT_MASTER_CH_P001",
      X = 15,
      Y = 12
    }
  }
  AddEnforceMissionUnits(initailUnitTable)
end

function ClassBattle:SpawnEnemyAndNeutralUnit_Implementation()
  local lv = 34
  SpawnUnit("N206", "UNIT_MASTER_CH_N206", "BATTLE_UNITPARAM_CH_N206", 29, 2, CHAR_DIR_NORTH, 0, 0)
  LevelUpToTargetLevel("N206", lv + 2)
  SpawnUnit("DAG1", "UNIT_MASTER_CH_M021_SLD_C_DAG", "BATTLE_UNITPARAM_CH_M021_SLD_C_DAG_RANK2", 27, 11, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("DAG1", lv)
  SpawnUnit("DAG2", "UNIT_MASTER_CH_M021_SLD_C_DAG", "BATTLE_UNITPARAM_CH_M021_SLD_C_DAG_RANK2", 27, 6, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("DAG2", lv)
  SpawnUnit("DAG3", "UNIT_MASTER_CH_M021_SLD_C_DAG", "BATTLE_UNITPARAM_CH_M021_SLD_C_DAG_RANK2", 30, 6, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("DAG3", lv)
  SpawnUnit("RID1", "UNIT_MASTER_CH_M022_SLD_C_RID", "BATTLE_UNITPARAM_CH_M022_SLD_C_RID_RANK2", 28, 13, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("RID1", lv)
  SpawnUnit("RID2", "UNIT_MASTER_CH_M022_SLD_C_RID", "BATTLE_UNITPARAM_CH_M022_SLD_C_RID_RANK2", 29, 14, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("RID2", lv)
  SpawnUnit("RID3", "UNIT_MASTER_CH_M022_SLD_C_RID", "BATTLE_UNITPARAM_CH_M022_SLD_C_RID_RANK2", 30, 3, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("RID3", lv)
  SpawnUnit("BOK1", "UNIT_MASTER_CH_M023_SLD_C_BOK", "BATTLE_UNITPARAM_CH_M023_SLD_C_BOK_RANK2", 29, 9, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("BOW1", lv)
  SpawnUnit("BOW1", "UNIT_MASTER_CH_M021_SLD_C_BOW", "BATTLE_UNITPARAM_CH_M021_SLD_C_BOW_RANK2", 22, 5, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("BOW1", lv)
  SpawnUnit("BOW2", "UNIT_MASTER_CH_M021_SLD_C_BOW", "BATTLE_UNITPARAM_CH_M021_SLD_C_BOW_RANK2", 12, 5, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("BOW2", lv)
  SpawnUnit("BOW3", "UNIT_MASTER_CH_M021_SLD_C_BOW", "BATTLE_UNITPARAM_CH_M021_SLD_C_BOW_RANK2", 26, 8, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("BOW3", lv)
  SpawnUnit("ROD1", "UNIT_MASTER_CH_M023_SLD_C_ROD", "BATTLE_UNITPARAM_CH_M023_SLD_C_ROD_RANK2", 28, 4, CHAR_DIR_SOUTH, 0, 0)
  LevelUpToTargetLevel("ROD1", lv)
  SpawnUnit("M031_01", "UNIT_MASTER_CH_M031", "BATTLE_UNITPARAM_CH_M031", 7, 5, CHAR_DIR_EAST, 0, 0)
  LevelUpToTargetLevel("M031_01", lv - 2)
  SpawnUnit("M031_02", "UNIT_MASTER_CH_M032", "BATTLE_UNITPARAM_CH_M032", 1, 5, CHAR_DIR_EAST, 0, 0)
  LevelUpToTargetLevel("M031_02", lv - 2)
  SpawnUnit("M031_03", "UNIT_MASTER_CH_M032", "BATTLE_UNITPARAM_CH_M032", 2, 4, CHAR_DIR_EAST, 0, 0)
  LevelUpToTargetLevel("M031_03", lv - 2)
end

function ClassBattle:SpawnAndChangeMapGimmick_Implementation()
end

function ClassBattle:PostSpawnUnit_Implementation()
end

function ClassBattle:PreStartBattle_Implementation()
  Introduction()
end

function Introduction()
  local tmpInputMode = SetActionInputMode(INPUT_MODE_GAME_UI)
  CloseMenuBattleAll()
  SetBattleCursorVisibility(false)
  ChangeIdleAnimationAllCharacter(AnimationType.Idle)
  MoveBattleCursor(4, 14)
  Wait(0.5)
  ChangeIdleAnimationAllCharacter(AnimationType.BattleIdle)
  OpenMenuBattleAll()
  SetBattleCursorVisibility(true)
  SetActionInputMode(tmpInputMode)
  ChangeTraceCamera(CAMERA_BLEND_CUBIC, 0.4, 2)
  _retry(SYS_WaitStageCameraBlend)
end

BattleEndCheckTable = {}
