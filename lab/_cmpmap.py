# gRPC Command oneof tag -> name (from proto)
grpc = {
1000:'interact',1001:'stop',1002:'work',1003:'move',1004:'create',1005:'addAttribute',
1010:'aiOrder',1011:'resign',112:'addWaypoint',1013:'pause',1016:'groupWaypoint',
1017:'groupAiOrder',1018:'unitAiState',1019:'guard',1020:'follow',1021:'patrol',1022:'scout',
1023:'formFormation',1033:'attackMove',1100:'make',1101:'research',1102:'build',1103:'game',
1104:'explore',1105:'buildWall',1106:'cancelBuild',1107:'attackGround',1110:'repair',
1111:'unload',1114:'gate',1115:'flare',1117:'unitOrder',1118:'diplomacy',1119:'queue',
1120:'setGatherPoint',1122:'sellCommodity',1123:'buyCommodity',1127:'townBell',
1128:'goBackToWork',1129:'multiQueue',1131:'deleteObjects'}
# mgz Action id -> name
mgz = {0:'ORDER',1:'STOP',2:'WORK',3:'MOVE',4:'CREATE',5:'ADD_ATTRIBUTE',6:'GIVE_ATTRIBUTE',
10:'AI_ORDER',11:'RESIGN',16:'ADD_WAYPOINT',18:'STANCE',19:'GUARD',20:'FOLLOW',21:'PATROL',
23:'FORMATION',33:'DE_ATTACK_MOVE',41:'DE_TRANSFORM',100:'MAKE',101:'RESEARCH',102:'BUILD',
103:'GAME',105:'WALL',106:'DELETE',107:'ATTACK_GROUND',108:'TRIBUTE',110:'REPAIR',
111:'UNGARRISON',112:'MULTIQUEUE',114:'GATE',115:'FLARE',119:'QUEUE',120:'GATHER_POINT',
122:'SELL',123:'BUY',126:'DROP_RELIC',127:'TOWN_BELL',128:'BACK_TO_WORK',129:'DE_QUEUE'}
print(f"{'mgzID':>5} {'mgz name':<16} {'grpc tag':>8} {'grpc name'}")
for mid,mn in sorted(mgz.items()):
    # grpc tag is mgz id + 1000 for most
    tag = mid+1000
    gn = grpc.get(tag) or grpc.get(mid) or '---'
    used = tag if grpc.get(tag) else (mid if grpc.get(mid) else '?')
    print(f"{mid:>5} {mn:<16} {str(used):>8} {gn}")
