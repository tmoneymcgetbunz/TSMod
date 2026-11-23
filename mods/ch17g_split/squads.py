"""Default Golden-route squads for the 20 recruits (user, 2026-11-21: balance power/role first, story ties second).
Plan and reasoning: mods/ch17g_plan.md. Shared by mods/ch17g_split/make_mod.py and mods/join_release/make_join.py.
Keys: B = Benedict's squad, R = Roland's, F = Frederica's (save byte 1 / 2 / 3).
"""
DEFAULT = {
    # Benedict (7)
    "N101": "B", "N007": "B", "N205": "B", "N004": "B", "N105": "B", "M103": "B", "N301": "B",
    # Roland (7)
    "N005": "R", "N106": "R", "N204": "R", "N008": "R", "N103": "R", "N206": "R", "N202": "R",
    # Frederica (6)
    "N104": "F", "N006": "F", "N009": "F", "N102": "F", "N207": "F", "N203": "F",
}
assert len(DEFAULT) == 20

# Split screen (level ms17s_x38_3team): free floor right of each squad's 3x3 block (squads at x 9-11; Roland y 6-8,
# Benedict y 10-12, Frederica y 14-16). Figures stand here, in table order. [read: A1_IN_Hall_WB grid]
SPOTS = {
    "R": [(12, 6), (13, 6), (12, 7), (13, 7), (12, 8), (13, 8), (12, 9)],
    "B": [(12, 10), (13, 10), (12, 11), (13, 11), (12, 12), (13, 12), (12, 13)],
    "F": [(12, 14), (13, 14), (12, 15), (13, 15), (12, 16), (13, 16)],
}

LUA_TABLE = "{" + ", ".join(f'{{"UNIT_MASTER_CH_{c}", "{k}"}}' for c, k in DEFAULT.items()) + "}"
LUA_CONST = ('local function tsmod_squad_const(k)\n'
             '  if k == "B" then return EPartyTeamBenedict elseif k == "R" then return EPartyTeamRoland end\n'
             '  return EPartyTeamFrederica\n'
             'end\n'
             'local function tsmod_squad_key(v)\n'
             '  if v == nil then return nil end\n'
             '  if v == EPartyTeamBenedict then return "B" elseif v == EPartyTeamRoland then return "R"\n'
             '  elseif v == EPartyTeamFrederica then return "F" end\n'
             '  return nil\n'
             'end\n')
