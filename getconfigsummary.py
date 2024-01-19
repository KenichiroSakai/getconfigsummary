# -*- coding: utf-8 -*-

'''スクリプトファイル

コマンドプロンプトより起動され、そこで入力されたコンフィグファイルに対しサマリ生成や
補助的情報の付与等を施したファイルを出力し、作業者の生産性向上の一助とする

Copyright (c) 2023-2024 Fujitsu Limited.  All rights reserved.

'''


__version__ = '1.01'


import sys
import os
import re
import getpass
import csv
import platform
import time
import argparse

from copy import deepcopy
from common.extract_ipaddress import extract_ipv4address, extract_ipv4network
from common.util import Tuple_Iterator, standard_out, CustomHelpFormatter, exclude_element, get_encode

drive = 'C:\\'; user = 'Users'; dir_dl = 'Downloads'; mfname = 'config.txt'; outname = 'out.txt'
mfsysname = 'config_sys.csv'; outsysname = 'config_out#'

uid = getpass.getuser()




def getconfigsummary(args: argparse.Namespace,
                     in_folder: str = os.path.join(drive, user, uid, dir_dl), 
                     out_folder: str = os.path.join(drive, user, uid, dir_dl)) -> None:

    '''configファイルのサマリーを抽出し出力ファイルを作成する
    
    引数:
    args    - コマンドラインからの入力引数(argparse.Namespaceのインスタンス)
    in_folder - 入力configファイル格納先
    out_folder - 出力ファイル格納先
    
    戻り値:なし
    
    処理対象ファイル説明：
    識別フラグ情報付きコンフィグファイル(system=True時有効)
    
    入力ファイル説明(csv形式、ファイル先頭行より開始しタイトル行は無し)
    カラム1: ○/- 0系で有効/無効
    カラム2: ○/- 2系で有効/無効
    カラム3: ○/- 1系で有効/無効
    カラム4: ○/- 3系で有効/無効
    カラム5: コマンド文字列
    
    入力ファイル例
    ○, -, ○, -, ip access-list vSAMPLE-TEST-NER-IN-ACL
    ○, -, ○, -, 10 permit ip 100.100.8.0 0.0.0.3 any
    ○, -, ○, -, 10 permit ip 100.100.8.4 0.0.0.3 any
    ○, -, ○, -, 20 permit ip 100.100.8.16 0.0.0.3 any
    ○, -, ○, -, 20 permit ip 100.100.8.20 0.0.0.3 any
    ...

    コンフィグファイル(system=False時有効)
    
    入力ファイル例(コマンドテキスト列)
    ip access-list vSAMPLE-TEST-NER-IN-ACL
    10 permit ip 100.100.8.0 0.0.0.3 any
    10 permit ip 100.100.8.4 0.0.0.3 any
    20 permit ip 100.100.8.16 0.0.0.3 any
    20 permit ip 100.100.8.20 0.0.0.3 any
    ...

    オプション指定として以下の引数をとる
    preview : args.preview_mode - プレビュー指定(True/False) - プレビュー版/従来版動作
    system : args.system_mode  - 系識別フラグ情報に従った系毎のコンフィグファイル出力指示(True/False) - 出力あり/なし    
    処理内容との対応：
                                 system
                        |   False   |   True   |
    --------------------------------------------
    preview = False     |    処理1  |   処理3   |    
    --------------------------------------------
    preview = True      |    処理2  |   処理4   |          
    ---------------------------------------------

    処理1 : 入力コンフィグファイルを元にサマリ出力(従来版)を実施する
    処理2 : 入力コンフィグファイルを元にサマリ出力(プレビュー版)を実施する
    処理3 : 識別フラグ情報付きコンフィグファイルを元にサマリ出力(従来版)するのに加え、
           系毎のコンフィグファイルの生成・出力を行う。
    処理4 : 識別フラグ情報付きコンフィグファイルを元にサマリ出力(プレビュー版)するのに加え、
           系毎のコンフィグファイルの生成・出力を行う。

    Windowsプロンプトからコマンド実行する際の入力引数と処理動作の対応
    
    >python getconfigsummary.py (引数)

    引数            実行内容 
    --------------  -------
    (なし)         : 処理1
    p, preview, -p : 処理2
    s, system, -s  : 処理3
    sp, ps, -ps    : 処理4


    内部変数の説明
    inlines : 入力コンフィグファイルをリスト形式で格納し検索処理に渡す為の格納域(list)
    system = False時 : 入力ファイルの各コマンド行(改行文字は除去)
    system = True時  : 識別フラグ情報付きコンフィグファイルのコマンド各要素列の行への転置

    sysflags : list(二次元リスト)
    識別フラグ情報付きコンフィグファイルの各系に対応するカラム列情報の行への転置を行い、
    さらに内部処理都合上、2系と1系の要素順を入れ替えたもの
    sysflags[0] : 0系で有効/無効(○/-)
    sysflags[1] : 1系で有効/無効(○/-)
    sysflags[2] : 2系で有効/無効(○/-)
    sysflags[3] : 3系で有効/無効(○/-)
    '''

    try:

        if args.f != None: # コマンドラインからのファイル名指定、又は標準入力指定
            if args.f != "stdin":
                in_path = os.path.join(os.getcwd(), args.f)
                if not os.path.exists(in_path):
                    print('ファイル ' + args.f + ' が見つかりません。')
                    return
            else:
                if args.system_mode:
                    print('標準入力からの識別フラグ情報付きコンフィグファイルには現状未対応です'); return
                    #input_csv = [row for row in csv.reader(sys.stdin)] # 文字コード変換への対応が必要
                else:
                    inlines = sys.stdin.read().splitlines() # リスト化
        
        else:
            if not os.path.exists(in_folder):
                raise FileNotFoundError
            
            print('入力ファイル格納先\n' + in_folder)
            if args.system_mode == True:
                s = input('コンフィグファイル名(系識別フラグ付き)を入力してください'+
                          '(省略時:'+ mfsysname +'):')
                fname = mfsysname if s == '' else s
            else:
                s = input('ファイル名を入力してください'+'(省略時:'+ mfname +'):')
                fname = mfname if s == '' else s
            in_path = os.path.join(in_folder, fname) 

            if not os.path.exists(in_path):
                print('ファイル ' + fname + ' が見つかりません。')
                return

        # ベンチマークテスト
        if args.benchmarktest == True:
            starttime = time.time()

        if "inlines" not in locals() and "input_csv" not in locals() :  # 名前の存在確認 
            enc = get_encode(in_path)
            if enc == None: 
                raise UnicodeError
            with open(in_path, "r", encoding=enc) as f:
                if args.system_mode:
                    input_csv = [row for row in csv.reader(f)]  # 二次元リスト
                else:
                    inlines = f.readlines()        

        if "input_csv" in locals():  # 名前の存在確認
            input_csv_T = [list(x) for x in zip(*input_csv)] # 転置
            if len(input_csv_T) < 5: 
                print('ファイル形式が違います'); return            

            sys_flags = []
            sys_flags.append(input_csv_T[0]); sys_flags.append(input_csv_T[2]) # 2系と1系を入れ替え
            sys_flags.append(input_csv_T[1]); sys_flags.append(input_csv_T[3])
            inlines = list(line for line in input_csv_T[4])
            sys_flags = [list(map(lambda s:s.strip(), slist)) for slist in sys_flags] # csv各要素の前後空白除去

        inlines = list(map(lambda s:s.lstrip().rstrip("\n"), inlines))  # 行頭の空白と改行除去

        # コマンド検索・出力処理
        result = CommandLevelList([],[])

        if args.reqno != None: # コマンドラインからのreqno指定有
            reqno_range = [elem for elem in args.reqno if elem < 16] # elemがint型であることはargparseにて保証済
        else:
            reqno_range = list(range(1,16))

        for i in reqno_range:
            result.extend(find_matching_line_in_commands(args, inlines, i))


        def data_out(path, data):  # ファイル出力用関数('Windows'または'Linux'のみを前提) 
            encoding='cp932' if platform.system() == 'Windows' else 'utf-8' 
            with open(path, 'w', encoding=encoding) as f:
                f.write("\n".join(data))        

        if args.f != None:
            for cmd_level in result.iter():
                # 行番号またはspan-listがない場合はデータのみ標準出力
                if "line_number" not in cmd_level[1] or "span-list" not in cmd_level[1]:
                    print(cmd_level[0]); continue
                
                standard_out(cmd_level[0], cmd_level[1]["line_number"], cmd_level[1]["span-list"], len(inlines), n=args.line_number , z=args.colorless)

            if args.benchmarktest == True:
                seconds = time.time() - starttime
                print ("processing takes " + '{:.3f}'.format(seconds) + " seconds")

            if args.json == True:
                import json
                for cmd_level in result.iter():
                    print(json.dumps(cmd_level[1], indent=4))
        else:
            if args.benchmarktest == True:
                seconds = time.time() - starttime
                print ("processing takes " + '{:.3f}'.format(seconds) + " seconds")            
            
            if not os.path.exists(out_folder):
                raise FileNotFoundError
            else:
                print('出力ファイル格納先\n' + out_folder)
                s = input('サマリーファイル名を入力してください'+'(省略時:'+ outname +'):')
                fname = outname if s == '' else s
                out_path = os.path.join(out_folder, fname) 

            if os.path.exists(out_path):
                if not get_yes_or_no('ファイルが存在します。上書きしますか?(Y/N)', retries=2):
                    return
                
            data_out(out_path, result.data)
            
        if args.system_mode:
            if args.f != None:
                out_folder = os.path.join(os.getcwd())
        #    if args.f == "stdin":
        #        return # 系毎のコンフィグファイルを出力する手段ないため、サマリ出力のみとしここで終了

            if not os.path.exists(out_folder):
                raise FileNotFoundError
        
            circles = [WHITE_CIRCLE, LARGE_CIRCLE, MEDIUM_WHITE_CIRCLE]
            
            s = input('系毎にコンフィグファイルを出力します。ファイル名を入力してください'+ \
                      '(省略時:'+ outsysname +'<系番号(0-3).txt> (<>内はスクリプトで生成)):')
            fname = outsysname if s == '' else s
            
            done = False
            for i in range(4):
                out = list(x for x, y in zip(inlines, sys_flags[i]) if y in circles)
                if out == []: continue
                out_path = os.path.join(out_folder, fname + str(i) + ".txt")
                if done == False: 
                    # 最初の出力時のみプロンプト出力
                    if os.path.exists(out_path):
                        done = True
                        if not get_yes_or_no('ファイルが存在します。上書きしますか?(Y/N)', 
                                             retries=2):
                            print("出力を中止しました。")
                            return
                data_out(out_path, out)                                           

        if args.f == None:
            print("データ出力が完了しました。")            
        else:
            if args.system_mode == True:        
                print("データ出力が完了しました。")


    except(RetryError):
        print('リトライ回数超過しました。')
    except(KeyboardInterrupt):
        print('\n')
        print('強制中断されました。')
    except(EOFError):
        print('ファイル読み込みに失敗しました。')
    except(UnicodeDecodeError, UnicodeError):
        print('文字コードを確認してください。')
    except(FileNotFoundError):
        print('ファイルまたはディレクトリが見つかりません。')
    except(IndexError):
        print('内部エラーです。')
        raise
    except(ValueError):
        print('再度入力してください。')
        raise
    except:
        raise
    finally:
        pass



def find_matching_line_in_commands(args, commands: list, reqno: int) -> 'CommandLevelList':
    '''対象コマンド抽出
    引数
    args     - コマンドラインからの入力引数(argparse.Namespaceのインスタンス)
    commands - コマンド列から成るリスト
    reqno    - 要望番号(1, 2, 3,... )
    戻り値
    タイトル説明と抽出済みコマンド列のリスト、およびそれに対応する情報(レベル/行番号/span)からなるリストを
    インスタンス変数として持つCommandLevelListオブジェクト
    例: 
    data
    ['(1)ACLと受信用経路フィルタ突合',
     '●ACL',
     'ip access-list vSAMPLE-TEST-NER-IN-ACL',
     '10 permit ip 100.100.8.0 0.0.0.3 any', 
     '10 permit ip 100.100.8.4 0.0.0.3 any', 
     ...
     '410 permit ip 105.105.168.0 0.0.0.15 any',
     '', 
     '●受信経路フィルタ', 
     'ip prefix-list vSAMPLE-001-TEST-NER-IN-PL seq 10 permit 102.102.0.0/16 le 32',
     'ip prefix-list vSAMPLE-001-TEST-NER-IN-PL seq 20 permit 103.103.181.0/25 le 32', 
     ...
     'ip prefix-list vSAMPLE-004-TEST-NER-IN-PL seq 230 permit 108.108.112.0/24 le 32'
     ...]
    levels
    [{'level':'0'},
     {'level':'0'},
     {'level':'1', 'line_number':1, 'span-list': [{'atype': 'INFO', 'error': None, 'span': (0, 14)}]}
     {'level':'2', 'line_number':2, 'span-list': [{'atype': 'INFO', 'error': None, 'span': (0, 2)}, 
                                                  {'atype': 'A4', 'error': None, 'span': (13, 24),...}]}
     {'level':'2', 'line_number':3, 'span-list': [{'atype': 'INFO', 'error': None, 'span': (0, 2)}, 
                                                  {'atype': 'A4', 'error': None, 'span': (13, 24),...}]}
     ...
     {'level':'2', 'line_number':50, 'span-list':[{'atype': 'INFO', 'error': None, 'span': (0, 3)}, 
                                                  {'atype': 'A4', 'error': None, 'span': (14, 27),...}]}
     {'level':'0'},
     {'level':'0'},
     {'level':'1', 'line_number':72, 'span-list':[{'atype': 'INFO', 'error': None, 'span': (0, 14)}, 
                                                  {'atype': 'INFO', 'error': None, 'span': (35, 41)},...}]}
     {'level':'1', 'line_number':73, 'span-list':[{'atype': 'INFO', 'error': None, 'span': (0, 14)}, 
                                                  {'atype': 'INFO', 'error': None, 'span': (35, 41)},...}]}
     ...
     {'level':'1', 'line_number':118,'span-list':[{'atype': 'INFO', 'error': None, 'span': (0, 14)}, 
                                                  {'atype': 'INFO', 'error': None, 'span': (35, 41)},...}]}
     ...]

    内部変数
    List : 抽出したコマンド列をCommandLevelListのインスタンスとして保持する内部格納域(list)
    '''
    List = []; cl = CommandList(commands)

    if reqno == 1:
        # ACLと受信用経路フィルタ突合
        
        p1 = pattern_ip_access_list
        p2 = pattern_seqno
        p3 = pattern_ip_prefix_list_IN_PL

        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2)
        cmds2 = cl.find_matching_line_for_each_config_level(p3, Lv=1)


        List.append(cmds1.search_command_info(ptn = 2))       
        List.append(cmds2.search_command_info(ptn = 2))
        
        _, e1 = cmds1.compare_commandlines(cmds2, ptn = 2)
        _, e2 = cmds2.compare_commandlines(cmds1, ptn = 2)

        data_ex = e1; data_ex.extend(e2) # エラーコマンド
        cmds3 = data_ex.renew_level(lv = "1") # levelsのすべての"level"要素について"1"に設定

        List.append(cmds3)
        
        if cmds2.to_cln() <= cmds1.to_cln():
            cmds4 = CommandLevelList([], [])
        else:
            cmds4 = (cmds2.to_cln() - cmds1.to_cln()).to_cll()
        
        List.append(cmds4)
        
    if reqno == 2:
        # Staticルートと「StaticルートをBGPに再配送するための経路フィルタ」突合  
        
        p1 = pattern_vrf_context
        p2 = pattern_ip_route_ipv4addr
        p3 = pattern_ip_prefix_list_STATIC_TO_BGP_PL
        
        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2, ptn=2)
        cmds2 = cl.find_matching_line_for_each_config_level(p3)   # Lv=1は省略可能
        List.append(cmds1.search_command_info(ptn=2))
        List.append(cmds2)
        
#       a)Staticルート:#2-1で取得
#       b)WAN向けStaticルート：#7-1で取得したWAN-IFアドレス
#       c)デフォルトルート：0.0.0.0/0
#       d)ダミースタティックルート：#6-1で取得(ダミーStaticルート(宛先が/32でかつ出力IFが「Ethernet X/X.XXX」のもの))
#       →a) - b) -c) -d)を表示

        p4 = pattern_interface_EthernetXXXX
        p5 = pattern_ip_address
        p6 = pattern_ip_route_ipv4addr_slash32_EthernetXXXX        

        cmds3 = cl.find_matching_line_for_each_config_level(p4, p5, Lv=2) # b)を取得
        defaultcll = CommandLevelList(default_route, [{"level":"1"}] * len(default_route), lv = "1") # c)を取得
        cmds4 = cl.find_matching_line_for_each_config_level(p6) # d)を取得
        
        cmds5 = (
                 cmds1.to_cln() -
                 cmds3.to_cln() -
                 defaultcll.to_cln() -
                 cmds4.to_cln()
                ).to_cll()     # a) - b) -c) -d)

        List.append(cmds5.search_command_info(ptn=2))
       
        if cmds2.to_cln() == cmds5.to_cln():
            cmds6 = CommandLevelList([], [])
        else:
            cmds6 = (cmds2.to_cln() - cmds5.to_cln()).to_cll()
            cmds6.extend((cmds5.to_cln() - cmds2.to_cln()).to_cll())  # 伸長

        List.append(cmds6.search_command_info(ptn=2))

    if reqno == 3:
        # 「StaticルートをBGPに再配送するための経路フィルタ」と「StaticルートをBGPに再配送するためのルートマップ」突合
        
        p1 = pattern_ip_prefix_list_STATIC_TO_BGP_PL
        p2 = pattern_route_map_STATIC_TO_BGP_MAP
        p3 = pattern_match_ip_address
       
        cmds1 = cl.find_matching_line_for_each_config_level(p1)
        cmds2 = cl.find_matching_line_for_each_config_level(p2, p3, Lv=2)
        List.append(cmds1)
        List.append(cmds2)

    if reqno == 4:
        # Directルート(LAN-IF設定)と「DirectルートをBGPに再配送するための経路フィルタ」突合

        p1 = pattern_interface_port_channel
        p2 = pattern_description_Bleaf_LAN
        p3 = pattern_ip_address
        p4 = pattern_ip_prefix_list_DIRECT_TO_BGP_PL

        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, p3, Lv=2)
        cmds2 = cl.find_matching_line_for_each_config_level(p4)
        List.append(cmds1)
        List.append(cmds2.search_command_info(ptn=2))

        cmds3 = cmds1.add_networkinfo() # ネットワーク情報を行頭に付加
        List.append(cmds3.search_command_info(ptn=2))

        if cmds2.to_cln() == cmds3.to_cln():
            cmds4 = CommandLevelList([], [])
        else:
            cmds4 = (cmds2.to_cln() - cmds3.to_cln()).to_cll()
            cmds4.extend((cmds3.to_cln() - cmds2.to_cln()).to_cll())
            
        List.append(cmds4)

    if reqno == 5:
        #「StaticルートをBGPに再配送するための経路フィルタ」「DirectルートをBGPに再配送するための経路フィルタ」と経路広告用フィルタ突合
        
        p1 = pattern_ip_prefix_list_STATIC_TO_BGP_PL
        p2 = pattern_ip_prefix_list_DIRECT_TO_BGP_PL
        p3 = pattern_ip_prefix_list_OUT_PL

        cmds1 = cl.find_matching_line_for_each_config_level(p1)
        cmds2 = cl.find_matching_line_for_each_config_level(p2)
        cmds3 = cl.find_matching_line_for_each_config_level(p3)
        List.append(cmds1)
        List.append(cmds2)
        List.append(cmds3)
        
    if reqno == 6:
        # ダミーSaticルートと、ダミーStaticルートに適用するBFD設定と、ダミーStaticルートを条件とするTrack設定突合
        
        p1 = pattern_ip_route_ipv4addr_slash32_EthernetXXXX
        p2 = pattern_ip_route_static_bfd_EthernetXXXX
        p3 = pattern_track_reachability
 
        cmds1 = cl.find_matching_line_for_each_config_level(p1)
        cmds2 = cl.find_matching_line_for_each_config_level(p2)
        cmds3 = cl.find_matching_line_for_each_config_level(p3)
        List.append(cmds1.search_command_info(ptn=2))
        List.append(cmds2)
        List.append(cmds3)
        
        # ダミーStaticルートのGWアドレスで、BFD設定を絞り込み
        cmds4 = cmds2.extract_ip_matched_line(cmds1, ptn = 1)
        List.append(cmds4)

        # ダミーStaticルートを条件とし、Track設定を絞り込み
        cmds5 = cmds3.extract_ip_matched_line(cmds1, ptn = 2)
        List.append(cmds5)

    if reqno == 7:
        # WAN-IFアドレスと、BGPネイバー設定の突合

        p1 = pattern_interface_EthernetXXXX
        p2 = pattern_ip_address
        p3 = pattern_router_bgp_asno
        p4 = pattern_neighbor

        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2)
        cmds2 = cl.find_matching_line_for_each_config_level(p3, p4, Lv=2, ptn=2)

        List.append(cmds1.search_command_info(ptn=2, strict=False))
        List.append(cmds2)

    if reqno == 8:
        # LoopbackIFと、BGPルータIDの突合

        p1 = pattern_interface_loopbackseqno
        p2 = pattern_ip_address
        p3 = pattern_router_bgp_asno
        p4 = pattern_router_id_ipv4addr
 
        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2)       
        cmds2 = cl.find_matching_line_for_each_config_level(p3, p4, Lv=2, ptn=2)
        List.append(cmds1)       
        List.append(cmds2)

    if reqno == 9:
        #WAN-IF設定「interface Ethernet XX.<Sub-IF番号>」と、WAN-IFで指定する「encapsulation dot1q <VLAN番号>」の突合
        
        p1 = pattern_interface_EthernetXXXX
        p2 = pattern_encapsulation_dot1q

        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2)
        List.append(cmds1)

    if reqno == 10:
        #LAN-IF(Port-Channel IF)の「interface port-channelXX.<Sub-IF番号>」と、LAN-IFで指定する「encapsulation dot1q <VLAN番号>」の突合
        
        p1 = pattern_interface_port_channel
        p2 = pattern_encapsulation_dot1q

        cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, Lv=2)
        List.append(cmds1)

    if reqno == 11:
        #「DirectルートをBGPに再配送するための経路フィルタ」と、「DirectルートをBGPに再配送するためのルートマップ」の突合

        p1 = pattern_ip_prefix_list_DIRECT_TO_BGP_PL
        p2 = pattern_route_map_DIRECT_TO_BGP_MAP
        p3 = pattern_match_ip_address

        p4 = pattern_DIRECT_TO_BGP_PL

        cmds1 = cl.find_matching_line_for_each_config_level(p1)
        cmds2 = cl.find_matching_line_for_each_config_level(p2, p3, Lv=2)

        List.append(cmds1.search_command_info(ptn = 3, pattern = p4))
        List.append(cmds2.search_command_info(ptn = 3, pattern = p4))
        
        if cmds1.to_cls(p4) == cmds2.to_cls(p4):
            cmds3 = CommandLevelList([], [])
        else:
            cmds3 = (cmds1.to_cls(p4) - cmds2.to_cls(p4)).to_cll()
            cmds3.extend((cmds2.to_cls(p4) - cmds1.to_cls(p4)).to_cll())

        List.append(cmds3)

    if reqno == 14:
        # BGP設定、staticルートをBGPに再配送するためのルートマップ、経路フィルタの突合
        
        p1 = pattern_router_bgp_asno
        p2 = pattern_vrf_LB_VRF
        p5 = pattern_match_ip_address
    
        def redistribute_info(p3,p4,p6)-> None:
            ''' Static/Directルート共通処理関数 '''
            
            cmds1 = cl.find_matching_line_for_each_config_level(p1, p2, p3, Lv=2, ptn=2)
            cmds2 = cl.find_matching_line_for_each_config_level(p4, p5, Lv=2)
            cmds3 = cl.find_matching_line_for_each_config_level(p6)
            return cmds1, cmds2, cmds3

        # Staticルート
        cll1s, cll2s, cll3s = redistribute_info(pattern_redistribute_static,
                                                pattern_route_map_STATIC_TO_BGP_MAP,
                                                pattern_ip_prefix_list_STATIC_TO_BGP_PL)
        
        # CommandLevelListオブジェクトの複製を渡す
        # コマンド検索条件の固定値(-STATIC-TO-BGP-PL等)のハイライト表現を残す(階層構造作成時の上書きを回避)
        List.append(deepcopy(cll1s)); List.append(deepcopy(cll2s)); List.append(deepcopy(cll3s))

        # Directルート          
        cll1d, cll2d, cll3d = redistribute_info(pattern_redistribute_direct,
                                                pattern_route_map_DIRECT_TO_BGP_MAP,
                                                pattern_ip_prefix_list_DIRECT_TO_BGP_PL)
        List.append(deepcopy(cll1d)); List.append(deepcopy(cll2d)); List.append(deepcopy(cll3d))

        p7 = pattern_STATIC_TO_BGP_MAP
        p8 = pattern_STATIC_TO_BGP_PL
        List.append(cll1s.make_hierachy(cll2s, p7, cll3s, p8, ptn=2)) # 階層構造作成

        p7 = pattern_DIRECT_TO_BGP_MAP
        p8 = pattern_DIRECT_TO_BGP_PL

        List.append(cll1d.make_hierachy(cll2d, p7, cll3d, p8, ptn=2))

    if reqno == 15:
        # ACL設定と、それに紐付くリストとの突合
        
        p1 = pattern_ip_access_group
        p2 = pattern_ip_access_list
        p3 = pattern_seqno
        
        cmds1 = cl.find_matching_line_for_each_config_level(p1)
        cmds2 = cl.find_matching_line_for_each_config_level(p2, p3, Lv=2)

        List.append(deepcopy(cmds1))
        List.append(deepcopy(cmds2))
        
        p4 = pattern_IN_ACL
        List.append(cmds1.make_hierachy(cmds2, p4, ptn=1)) # 階層構造作成


    # cll(CommandLevelList)インスタンスからコマンド列で構成されるリストを取り出し、
    # サブリストとしてwkに積み、CommandLevelListのリストを作成
    wk = [cll.insert_empty_string() for cll in List]

    # 検索結果が[](空リスト)の場合の措置
    commandlevellists = [L if L.data != [] else CommandLevelList(["無し", ""], [{"level":"0"}, {"level":"0"}]) for L in wk]    

    if args.f == None: # 標準出力(コマンドラインからの入力ファイル名指定無し)の場合
        messages = ['見つかりました。' if L != [] else '検索対象が見つかりません。' for L in wk]
        frame = '#{}-{}: {}'
        for i, r in enumerate(messages, 1):       # 1から開始
            if title_dict_for_each_reqno[str(reqno)][i-1]['kind'] == 's':  # 1始まりのため-1
                print(frame.format(reqno, i, r))

    # 各要望番号に対応する出力結果へのタイトル付与  
    outline = CommandLevelList([],[])
    for i in range(len(commandlevellists)):
        if args.f == None: # ファイル出力
            # プレビュー版判定
            if args.preview_mode or (title_dict_for_each_reqno[str(reqno)][i]['kind'] == 's'):
                for title in title_dict_for_each_reqno[str(reqno)][i]['title']:
                    outline.extend(CommandLevelList([title],[{"level":"0"}])) # 伸長
                outline.extend(commandlevellists[i])
        else:
            # 標準出力対象か否かの判定
            if (title_dict_for_each_reqno[str(reqno)][i]['print'] == 'p'):
                for title in title_dict_for_each_reqno[str(reqno)][i]['title']:
                    outline.extend(CommandLevelList([title],[{"level":"0"}])) 
                outline.extend(commandlevellists[i])

    return outline


# 正規表現用パーツ群
# 簡略版ipv4アドレス定義
# A.B.C.Dの各オクテットが0,00,000～999であるもの(0～255に限定しない)

ipv4_address = r'''
    (?:[0-9]{1,3}\.){3}[0-9]{1,3}
    '''

# Ethernet定義(Xまたはxの表記を許可)
# 例: Ethernetx/20.XXX
EthernetXXXX_simple = r'''
    \s{1}       # 空白1文字
    (Ethernet)
    (?:[0-9]{1,}|X{1,}|x{1,})
    /
    (?:[0-9]{1,}|X{1,}|x{1,})
    \.
    (?:[0-9]{1,}|X{1,}|x{1,})
    (?:\s{1}|$) # 空白1文字または行末
    '''

# Ethernet定義(数字のみを許可)
# 例: Ethernet6/20.210
EthernetXXXX_strict = r'''
    \s{1}(Ethernet)[0-9]{1,}/[0-9]{1,}\.[0-9]{1,}
    (?:\s{1}|$)
    '''

# port-channel定義(数字のみを許可)
# 例: port-channel5.2110
port_channel_strict = r'''       
    \s{1}(port-channel)[0-9]{1,}\.[0-9]{1,}
    (?:\s{1}|$)
    '''

# コマンド列抽出用正規表現
#
# 行頭アンカー「^」,空白一文字「\s{1}」,文字の切れ目「\b」,行末「$」の使い分けの基本的考え方
# コマンド検索用パターンの場合
# - 「^」から開始
# - 検索対象パターンの後に、パターンには含まない別の任意文字が期待される場合は(「\b」ではなく)「\s{1}」で終了
# - そのあとに「.*」(任意文字の0回以上),「.+」(任意文字の1回以上)は付与しない(行末までの余分な検索をさせない)
#   例: pattern_ip_access_list(ACL一行目)の定義において　
#   'ip access-list TEST-ACL' => 検索成功(後半の「TEST-ACL」は今回の検索対象には含まれない任意の文字) 
# 　'ip access-list '         => 検索成功(本来は文字列(アクセスリスト名称)が続く所、空白で終わっているが成功とする)
#   'ip access-list'          => 不成功(「\b」で終わらせれば成功になるケース)
# - 検索対象パターンの最後が行末となりうる場合は「\b」あるいは「$」で終了
# - 標準出力時のハイライト(色付け)表現を行う文字列キャプチャはその部分をカッコ「(...)」で囲む(m.group([n])で取得)
#
# 文字列抽出(キャプチャ)用パターンの場合
# - キャプチャしたい文字列を含むコマンド先頭(行頭)に「^」、キャプチャ対象文字列をカッコ「(...)」で囲み、最後に「\b」を置く
#
# 正規表現パターンはあらかじめデバッグ済みであることを前提に、re.errorのキャッチはしない
# また、不適切なパターン定義によっては、search/matchによる検索に多大の時間を要する、または正規表現エンジンから
# 戻ってこない等ケースもありうるが、前述の内容と同様、タイムアウト監視等の処理は行わない
# 
# 以下の最上位階層で正規表現をコンパイルおよび結果の内部キャッシングを実施し、実際の検索処理では
# そのコンパイル済みオブジェクトを使用する

# 'ip access-list'で始まるコマンド(ACL一行目)
pattern_ip_access_list = re.compile(r'''          
    ^                     # 行頭
    (                     # キャプチャ開始
    ip                    # 検索対象文字列
    \s{1}                 # re.VERBOSE使用の為、空白を明示
    access-list           # 検索対象文字列
    )                     # キャプチャ終了
    \s{1}                 #
    ''', re.VERBOSE)

# 数字1桁~(seqno)で始まるコマンド(ACL二行目以降)
pattern_seqno = re.compile(r'''          
    ^([0-9]{1,})          # 数字1桁~
    ''', re.VERBOSE)

# 受信用経路フィルタ
# 'ip prefix-listで始まり、任意の文字が続いた後、'_IN_PL'が出現するコマンド
pattern_ip_prefix_list_IN_PL = re.compile(r'''       
    ^(ip\s{1}prefix-list)\s{1}.*(-IN-PL)\s{1}
    ''', re.VERBOSE)

# 経路広告用フィルタ
# 'ip prefix-list'で始まり、任意の文字が続いた後、'-OUT-PL'が出現するコマンド
pattern_ip_prefix_list_OUT_PL = re.compile(r'''
    ^(ip\s{1}prefix-list)\s{1}.*(-OUT-PL)\s{1}
    ''', re.VERBOSE)

# 再配送定義(Static)
pattern_redistribute_static = re.compile(r'''       
                ^(redistribute\s{1}static)\s{1}
                ''', re.VERBOSE)

# 再配送定義(Direct)
pattern_redistribute_direct = re.compile(r'''       
                ^(redistribute\s{1}direct)\s{1}
                ''', re.VERBOSE)

# 'vrf context'で始まるコマンド(Staticルート一行目)
pattern_vrf_context = re.compile(r'''  
    ^(vrf\s{1}context)\s{1}
    ''', re.VERBOSE)

# 'ip route (ipv4アドレス)'で始まるコマンド(Staticルート二行目以降)
pattern_ip_route_ipv4addr = re.compile(r'''          
    ^(ip\s{1}route)\s{1}'''       + \
    
    ipv4_address                  + \
    
    r'''/
    [0-9]{1,2}  # アドレスプレフィックス値(数字1-2桁, 0～99)
    ''', re.VERBOSE)


# Static/DirectルートをBGPに再配送するための経路フィルタ/ルートマップ定義
def ptn1(cmd: str, ds: str, pm: str)-> 're.Pattern':
    '''正規表現パターン生成用関数
    入力: 
          cmd(str) : "ip prefix-list"
                     "route-map"
          ds(str)  : "DIRECT"/"STATIC"
          pm(str)  : "PL"/"MAP"
    戻り値: re.compile()結果
    '''

    return re.compile(r'''
        ^        # 行頭
        ('''                        + \
        cmd                         + \
        r''')
        \s{1}.*  # 空白1文字+貪欲マッチ           
        ('''                        + \
        ds                          + \
        r'''-TO-BGP-'''             + \
        pm                          + \
        r''')\s{1}'''
        , re.VERBOSE)

# Static/DirectルートをBGPに再配送するための経路フィルタならびにルートマップ定義
#pattern_ip_prefix_list_STATIC_TO_BGP_PL = ptn1("ip\s{1}prefix-list", "STATIC", "PL")
#pattern_ip_prefix_list_DIRECT_TO_BGP_PL = ptn1("ip\s{1}prefix-list", "DIRECT", "PL")

# 20240104
#  raw 文字列記法の使用:Python 3.12にてSyntaxWarning: invalid escape sequence '\s'となることの回避
#
pattern_ip_prefix_list_STATIC_TO_BGP_PL = ptn1(r"ip\s{1}prefix-list", "STATIC", "PL")
pattern_ip_prefix_list_DIRECT_TO_BGP_PL = ptn1(r"ip\s{1}prefix-list", "DIRECT", "PL")
pattern_route_map_STATIC_TO_BGP_MAP     = ptn1("route-map",          "STATIC", "MAP")
pattern_route_map_DIRECT_TO_BGP_MAP     = ptn1("route-map",          "DIRECT", "MAP")


# 'interface port-channelX.XXX'で始まるコマンド
pattern_interface_port_channel = re.compile(r'''       
    ^(interface
    \s{1}
    port-channel)
    (?:[0-9]{1,}|X{1,}|x{1,})
    \.                      
    (?:[0-9]{1,}|X{1,}|x{1,})
    (?:\s{1}|$)
    ''', re.VERBOSE)

# 'description Bleaf (任意の文字)-LAN>'で始まるコマンド
pattern_description_Bleaf_LAN = re.compile(r'''
    ^(description\s{1}Bleaf).*(-LAN)[>|\b]
    ''', re.VERBOSE)
                         
# 'ip address'で始まるコマンド(例'ip address 192.168.16.0/28)
pattern_ip_address = re.compile(r'''       
    ^(ip\s{1}address)\s{1}
    ''', re.VERBOSE)

# 'match ip address'で始まるコマンド
pattern_match_ip_address = re.compile(r'''
                ^(match\s{1}ip\s{1}address)\s{1} 
                ''', re.VERBOSE)

# 'ip access-group'で始まるコマンド
pattern_ip_access_group = re.compile(r'''       
                ^(ip\s{1}access-group)\s{1}
                ''', re.VERBOSE)

# ダミーStaticルート
# 'ip route A.B.C.D/32 Ethernetx/xxx'で始まるコマンド
pattern_ip_route_ipv4addr_slash32_EthernetXXXX = re.compile(r'''
    ^(ip\s{1}route)\s{1}'''    + \
    ipv4_address               + \
    r'''/32'''                 + \
    EthernetXXXX_simple
    , re.VERBOSE)

# ダミーStaticルートに適用するBFD設定
# 'ip route static bfd EthernetX/X.XXX'で始まるコマンド
pattern_ip_route_static_bfd_EthernetXXXX = re.compile(r'''       
                ^(ip\s{1}route\s{1}static\s{1}bfd)''' + EthernetXXXX_simple
                , re.VERBOSE)

# Track設定
#「track 99 ip route 100.105.225.193/32 reachability」のように「track ～ reachability」で始まるコマンド
pattern_track_reachability = re.compile(r'''
                ^(track)\s{1}.*(reachability)
                ''', re.VERBOSE)
                         
# WAN-IF
# 'interface EthernetX/X.XXX'で始まるコマンド
pattern_interface_EthernetXXXX = re.compile(r'''
                ^(interface)''' + EthernetXXXX_simple
                , re.VERBOSE)

# 'interface loopbackxx'(LoopbackID)で始まるコマンド
pattern_interface_loopbackseqno = re.compile(r'''
                ^(interface\s{1}loopback)(?:[0-9]{1,}|(?:x|X){1,})
                (?:\s{1}|$)
                ''', re.VERBOSE)

# 'encapsulation dot1q' で始まるコマンド
pattern_encapsulation_dot1q = re.compile(r'''
                ^(encapsulation\s{1}dot1q)\s{1}
                ''', re.VERBOSE)

# BGP設定関連
# 'router bgp (asno)'で始まるコマンド
pattern_router_bgp_asno = re.compile(r'''
                ^(router\s{1}bgp)\s{1}(?:[0-9]{1,}|(?:x|X){1,})
                ''', re.VERBOSE)

# BGPネイバー設定:'neighbor'で始まるコマンド
pattern_neighbor = re.compile(r'''
                ^(neighbor)\s{1} 
                ''', re.VERBOSE)

# BGPルータID: router-id (ipv4addr)で始まるコマンド
pattern_router_id_ipv4addr = re.compile(r'''
                ^(router-id)\s{1}
                ''', re.VERBOSE)

# bgp定義中のvrf定義
pattern_vrf_LB_VRF = re.compile(r'''       
                ^(vrf)\s{1}.*-LB-VRF 
                ''', re.VERBOSE)


# 文字列キャプチャ用正規表現
# 空白と単語の末尾で囲まれ、かつ「DIRECT-TO-BGP-PL」で終わる文字列で、空白が最も右に位置する(すなわち長さが最短の)もの 
# 例 : コマンド行:'redistribute direct route-map vSAMPLE-004-TEST-DIRECT-TO-BGP-PL'
#      抽出文字列:'vSAMPLE-004-TEST-DIRECT-TO-BGP-PL'

def ptn(ds: str, pm: str)-> 're.Pattern':
    '''正規表現パターン生成用関数
    入力: ds(str) : "DIRECT"/"STATIC"
          pm(str) : "PL"/"MAP"
    戻り値: re.compile()結果
    '''
    return re.compile(r'''
        ^      # 行頭
        .+     # 空白の前に任意の1文字以上を期待、貪欲マッチ(.*(任意の0文字以上)とはしない)
        \s{1}  # 空白1文字             
        (      # キャプチャ対象グループ開始
        .*     # 貪欲マッチ(ここでは貪欲でも非貪欲マッチでも結果は同じ、内部動作が異なるのみ)
        '''                         + \
        ds                          + \
        r'''-TO-BGP-'''             + \
        pm                          + \
        r'''
        )      # キャプチャ対象終了
        \b     # 単語の末尾
        ''', re.VERBOSE)

pattern_DIRECT_TO_BGP_PL  = ptn("DIRECT", "PL")
pattern_DIRECT_TO_BGP_MAP = ptn("DIRECT", "MAP")
pattern_STATIC_TO_BGP_PL  = ptn("STATIC", "PL")
pattern_STATIC_TO_BGP_MAP = ptn("STATIC", "MAP")


# 空白と単語の末尾で囲まれ、かつ「-IN-ACL」で終わるもの文字列で、空白が最も右に位置する(すなわち長さが最短の)もの 
# 例 : コマンド行:'ip access-group vSAMPLE-TEST-NER-IN-ACL in'
#      抽出文字列:'vSAMPLE-TEST-NER-IN-ACL'

pattern_IN_ACL = re.compile(r'''
    ^.+\s{1}(.*-IN-ACL)\b
    ''', re.VERBOSE)
                
                
class CommandList:
    '''
    コマンド列からなるリストをインスタンス変数に持ち、そのインスタンスオブジェクトに付随する操作を
    メソッドとして定義するクラス
    '''

    def __init__(self, data: list) -> None:
        '''インスタンス変数の初期化 
        引数: data(リストを前提、リストでなければ例外をスロー) 
        戻り値:なし
        '''
        if data is not None:
            if not isinstance(data, list):
                raise TypeError('{} is not supported'.format(type(data)))
        
        self.data = data


    def __repr__(self):
        ''' str表記を返す '''
        return repr(self.data) 
    
    
    def __len__(self):
        ''' リストの長さを返す'''
        return len(self.data)
        

    def __iter__(self):
        ''' dataインスタンス(リスト)の各要素を逐次返すイテレーターの初期化'''
        return iter(self.data)  
    
    
    def find_matching_line_for_each_config_level(self, *args: 're.Pattern', Lv: int = 1, ptn: int = 1, size: int = 30) -> 'CommandLevelList':
        '''対象コマンドを抽出する(configレベル毎のプロセス)
        引数
        args : コマンド検索に使用される正規表現パターン
         Lv = 1の場合
          - args[0] : Lv1-level1でのコマンド検索用
         
         Lv = 2の場合
          - args[0] : level1でのコマンド検索用
          - args[1] : level2でのコマンド検索用その1
          - args[2] : level2でのコマンド検索用その2
        Lv   : 1または2
        ptn  : 検索パターン
        size : 最後データの取得行数
        
        戻り値:
        抽出されたコマンド列およびレベル情報、等をインスタンス変数として持つCommandLevelListのインスタンス
        data   : 抽出されたコマンド列(list)
        levels : レベル情報、コマンド行番号、正規表現によるキャプチャデータに関するspan-list情報からなる辞書のリスト(list)
          ・コマンドレベル情報(キー項目:"level")(str): "1", "2", ...
          ・コマンド行番号:(キー項目:line_number)(int): 1始まり
          ・コマンド一行分のspan要素から構成される単数または複数の辞書のリスト(キー項目:"span-list")(list)

          span-listの説明 : 1コマンド内の以下の情報を格納する辞書 
          ・タイプ(キー項目:"atype")
          ・エラー有無(キー項目:"error")
          ・span情報(start/stop位置を示すintのタプル)(キー項目:"span")
          複数の辞書からなる1リストが1コマンドに対応
          - コマンド検索不成功(m==None)またはマッチなしlen(m.groups())==0の場合 - "span-list":[] # 空きリスト
          - コマンド検索成功(m!=None)かつマッチ有りlen(m.groups())!=0の場合
                (span(0)(マッチ全体)は取得しない)
                len(m.groups())=1の場合の例 - "span-list":[{"atype":"INFO", "error":None, "span":(17,19)},]
                len(m.groups())=2の場合の例 - "span-list":[{"atype":"INFO", "error":None, "span":(17,19)},
                                                          {"atype":"INFO", "error":None, "span":(22,25)},]
        levelsの例:
          [{"level": "0", },                               # "level" = "0"で"span-list"要素がないケース
           {"level": "0","line_number":3, "span-list":[]}, # "level" = "0"で"span-list"要素が[](空き)のケース     
           {"level": "1","line_number":50,"span-list":[{"atype":"INFO", "error":None, "span":(17,19)},],..}
           ...]
        lv     : 処理対象レベル(CommandLevelListにおけるコマンド抽出処理において、複数存在する対象レベルのうち
                 どのレベルを処理するかを指定)(str)
        
        処理詳細
        検索パターン(args) レベル(Lv)  パターン(ptn) 最終データ
        (カッコは省略可)                            取得行数(size) 処理概要
        ----------------- ---------- ------------- ------------- -------------- ------------------------------------------
        args[0]           1(default) -             -             検索パターンで全行検索し、ヒットした行を抽出
        args[0],args[1]   2          1(default)    -             まず、args[0]でヒットした行を抽出、
                                                                 次に、その次の行よりargs[1]で検索、
                                                                 ヒットするまで読み飛ばし、ヒットしたら都度抽出、
                                                                 別のコマンドが現れたら検索処理を抜ける

        args[0],args[1]   2          1(default)    -             まず、args[0]でヒットした行を抽出、
        ,args[2]                                                 次に、その次の行よりargs[1]とargs[2]で検索を実施、
                                                                 ヒットするまで読み飛ばし、ヒットしたら都度抽出、
                                                                 args[1]で別のコマンドがヒットしても検索処理を継続
                                                                 args[2]で別のコマンドがヒットしたら検索処理を抜ける

        args[0],args[1]   2          2             -             まず、args[0]でヒットした行を抽出、
        (,args[2])                                               次に、その次の行よりargs[1](とargs[2])で検索を実施、
                                                                 別のコマンドがヒットしても次のLv1コマンド直前まで検索処理を継続
                                                                 最終ブロックは最終行まで検索

        args[0],args[1]   2          3             30(default)   まず、args[0]でヒットした行を抽出、
        (,args[2])                                               次に、その次の行よりargs[1](とargs[2])で検索を実施、
                                                                 別のコマンドがヒットしても次のLv1コマンド直前まで検索処理を継続
                                                                 最終ブロックはsizeで指定された取得行数分のみ検索

        内部変数
        - command_levels : 
          検索でヒットしたコマンドのレベル情報("1", "2", ...)を元コマンドのindexと同一位置に保持するリスト。
          処理後に本リスト情報を元にコマンド列を取り出すのに使用。検索ヒットしなかったコマンド位置には"None"を格納
          例
          commands =       [.... .., Lv1-cmd, Lv2-1cmd, Lv2-2コマンド, Lv2-2コマンド,  ...]
          command_levels = [None,.., "1",     "2.1",    "2.2",        "2.2",    None, ...]

        - command_lineno : Lv1コマンドのindex番号から成るリスト(最小番号0)。この情報を元にLv2コマンド検索を開始する。
          [0番目のLv1-cmdの行番号, 1番目のLv1-cmdの行番号, 2番目のLv1-cmdの行番号,...]

        - spans : 検索結果のマッチオブジェクトの一時的格納用リスト
          [None,.., re.match,... ,  re.match,...    None,...]

        - line_numbers : コマンド行番号を格納したリスト(開始番号=1)
        '''
        
        commands = self.data
        command_levels, spans = [None] * len(commands), [None] * len(commands)
        line_numbers = list(i+1 for i in range(len(self)))

        if Lv == 1:
            p1 = args[0]
            
            for i in range(len(commands)):
                m = re.search(p1, commands[i])
                if m:
                    command_levels[i] = "1"; spans[i] = m
        
        elif Lv == 2:
            if len(args) == 2:
                p1 = args[0]; p2 = args[1]
            elif len(args) >= 3:
                p1 = args[0]; p2 = args[1]; p3 = args[2]

            # Step1 - Lv1コマンドリスト内行番号取得
            command_lineno = []

            for i in range(len(commands)):
                m = re.search(p1, commands[i])
                if m:
                    command_lineno.append(i); spans[i] = m
            
            # Lv2コマンドの抽出
            for i in range(len(command_lineno)):

                # Step2 - スライス最終番号の設定
                if i != len(command_lineno) - 1:
                    last = command_lineno[i+1]
                else:
                    if ptn == 1 or ptn == 2:
                        last = len(commands)
                    elif ptn == 3:
                        last = min(command_lineno[i] + size, len(commands))
                    
                found = False
                
                # Step3 - コマンド検索処理
                sl = commands[command_lineno[i] : last]   # スライス
                for j in range(len(sl)):
                    
                    m = re.search(p1, sl[j])
                    if m:
                        command_levels[command_lineno[i]+j] = "1"; spans[command_lineno[i]+j] = m
                        continue    # Lv1コマンド、次のfor反復へ
                        
                    if len(args) == 2:
                        if ptn == 1:
                            m =re.search(p2, sl[j])
                            if m:
                                found = True
                                command_levels[command_lineno[i]+j] = "2"; spans[command_lineno[i]+j] = m
                            else:
                                if found == False:
                                    continue  # 次のfor反復へ
                                else:
                                    break   # 直近のfor文を抜ける(次のLv1コマンドの要素の処理へ)

                        if ptn == 2 or ptn == 3:                        
                            m = re.search(p2, sl[j])
                            if m:
                                # p2 = args[1]は別のコマンドが現れても処理を継続
                                command_levels[command_lineno[i]+j] = "2"; spans[command_lineno[i]+j] = m

                    elif len(args) >= 3:
                        if ptn == 1:
                            m = re.search(p2, sl[j])
                            if m:
                                command_levels[command_lineno[i]+j] = "2.1"; spans[command_lineno[i]+j] = m
                            else:
                                m = re.search(p3, sl[j])
                                if m:
                                    found = True
                                    command_levels[command_lineno[i]+j] = "2.2"; spans[command_lineno[i]+j] = m                                    
                                else:
                                    if found == False:
                                        continue
                                    else:
                                        break
                                        
                        if ptn == 2 or ptn == 3:                        
                            m = re.search(p2, sl[j])
                            if m:
                                command_levels[command_lineno[i]+j] = "2.1"; spans[command_lineno[i]+j] = m
                            else:
                                m = re.search(p3, sl[j])
                                if m:
                                    command_levels[command_lineno[i]+j] = "2.2"; spans[command_lineno[i]+j] = m
        
        spans_s = spans
        for i in range(len(spans_s)):
            L = []
            if spans_s[i] != None:
                if len(spans_s[i].groups()) != 0:
                    for j in range(len(spans_s[i].groups())):
                        L.append({"atype":"INFO", "error":None, "span":spans_s[i].span(j+1), "info":spans_s[i].group(j+1)})
            spans[i] = L 

        # levels情報作成(辞書のリスト)
        lvls = list({"level": lv, "line_number":line_number, "span-list":span} for lv, line_number, span in zip(command_levels, line_numbers, spans) if lv != None)

        # lv:処理対象レベル-最後に抽出したコマンドのレベルを設定、要素数が0の場合は"0"を設定
        target_level = lvls[-1]["level"] if lvls != [] else "0"

        return CommandLevelList(list(cmd for level, cmd in zip(command_levels, commands) if level != None), \
                                 lvls, lv=target_level)


    def matches_to_pattern(self, ptn: int, pattern: str or 're.Pattern' = "")-> (list, list):
        '''正規表現パターンの内容で抽出した結果を返す(ipaddress型)
        引数:
        pattern ：正規表現パターン
        ptn : 比較対象
         1 : ipv4address
         2 : ipv4network
         3 : 通常のstr検索
        戻り値(タプル):
        1. インスタンスに保持されたリストの各要素から正規表現パターンの内容で抽出した結果(strのリスト)を
           各要素に対応するindex場所に詰めて返す
           マッチした要素が無い場合はNoneを詰める
        2. マッチする要素が無い場合の元コマンドが格納されたリスト(エラーメッセージと元コマンド列のタプルのリスト)
        
        例(ptn=1)
        入力
        ["router-id 100.100.9.1", "router-id 100.100.9.5", "router-id 100.100.9.17", "router-id 100.100.9.21",]
        戻り値(matches)
        ['100.100.9.1', '100.100.9.5', '100.100.9.17', '100.100.9.21',]
        戻り値(err_out)
        [None, None, None, None,]

        例(ptn=2)
        入力
        ["100 permit ip 101.101.161.128 0.0.0.127 any",
         "110 permit ip 102.102.0.0 0.0.255.255 any",
         "120 permit ip 103.103.181.0 0.0.0.127 any",
         "130 permit ip 103.103.183.0 0.0.255.255 any", #エラーケース
        ]
        戻り値(matches)
        ['101.101.161.128/25',
         '102.102.0.0/16',
         '103.103.181.0/25', 
         None,            #エラーの場合はNone
        ]
        戻り値(err_out)
        [None, 
         None, 
         None, 
         ("検索エラー:", "130 permit ip 103.103.183.0 0.0.255.255 any"), # エラーメッセージと元コマンド列のタプル 
        ]
        '''

        matches = []; err_out = []  
        
        for line in self:
           
            if ptn == 1:
                r = extract_ipv4address(line)

                if r == ():
                    rtn = None
                    err_out.append(("検索エラー" + ":", line)) # タプル
                else:
                    rtn = r[0]["ipaddr"]
                    if r[0]["error"] != None:
                        err_out.append((r[0]["error"] + ":", line))
                    else:
                        err_out.append(None)
 
            elif ptn == 2:
                r = extract_ipv4network(line, strict=True)

                if r == ():
                    rtn = None
                    err_out.append(("検索エラー" + ":", line))
                else:
                    rtn = r[0]["ipaddr"]
                    if r[0]["error"] != None:
                        err_out.append((r[0]["error"] + ":", line))
                    else:
                        err_out.append(None)
                     
            elif ptn == 3:
                m = re.search(pattern, line)
                if m:
                    rtn = m.groups()
                    err_out.append(None)                    
                else:
                    rtn = None
                    err_out.append(("検索エラー" + ":", line))

            matches.append(rtn)

        return matches, err_out


    def get_span_info(self, ptn: int, pattern: str or 're.Pattern' = "", strict:bool = True)-> list:
        '''正規表現パターンの内容で得たspan結果を返す
        引数:
        ptn : 比較対象
         1 : ipv4address
         2 : ipv4network
         3 : 通常のstr検索
        pattern ：正規表現パターン
        戻り値
        1コマンドに対応する結果(辞書のタプル)の複数コマンド分を格納するリストを返す
        ptn=1,2の場合の戻り値の例(extract_ipv4addressの戻り値が設定されている)
        [...,
         ({"atype":"A4", "error":None, "span":(9,23), "ipaddr": "192.168.100.64",}, \
          {"atype":"M4", "error":None, "span":(23,24),}, \
          {"atype":"M4", "error":None, "span":(24,26),}, \
         ), ...]

        ptn=3の場合の戻り値の例
        [...,   
         (),                                                 # len(m.groups())=0の場合(マッチ要素無しのコマンド)
         ({"atype":"KEY", "error":None, "span":(5,7)},), # len(m.groups())=1の場合
         ({"atype":"KEY", "error":None, "span":(5,7)},
          {"atype":"KEY", "error":None, "span":(10,15)},),  #len(m.groups())=2の場合
        ...]
        備考 : match全体(Match.group(0))に対応するspan(0)は、ここでは取得しない
        '''
        L = []
        for command in self:
            if ptn == 1:
                L.append(extract_ipv4address(command))
            if ptn == 2:
                L.append(extract_ipv4network(command, strict=strict))
            if ptn == 3:
                m = re.search(pattern, command)
                if m:
                    L2 = []                    
                    if len(m.groups()) == 0: pass
                    for i in range(len(m.groups())):
                        L2.append({"atype":"KEY", "error":None, "span":m.span(i+1), "key":m.group(i+1)})
                    L.append(tuple(L2))
                else:
                    L.append(tuple())
        return L


    def extract_ip_matched_line(self, filter: 'CommandList', ptn: int = 1)-> 'CommandList':
        '''インスタンス変数(リスト)を入力されたコマンドリストとパターン内容でフィルタリングし合致した要素を返す
        引数:
        fliter ：比較対象が設定されたリスト('CommandList'型)
        ptn : 比較対象
              1 : ipv4address
              2 : ipv4network
        戻り値 : 絞り込んだ結果を設定したCommandListインスタンス
        
        処理概要(ptn=1の場合)
        入力
        self:   ["router-id 1.1.1.1", "router-id 2.2.2.2", "router-id 256.256.256.256", "router-id 4.4.4.4",]
        filter: ["ip address 1.1.1.1", "ip address 999.999.999.999", "ip address 4.4.4.4",]

        Step1:
        正規表現でマッチした要素(タプル)から成るリストの作成、マッチ要素が無い場合およびエラー発生の場合はNone
        形式
        matches_target: ['1.1.1.1', '2.2.2.2', None , '4.4.4.4',]
        matches_filter: ['1.1.1.1', None, '4.4.4.4',]
        
        Step2: キー項目の積集合を取り、Noneの要素を削除
        intersection_keys: {'1.1.1.1', '4.4.4.4',}

        Step3: 条件にマッチしたコマンドを抽出、マッチしなかった要素に対してはNoneを設定
        matches_target(x): ['1.1.1.1', '2.2.2.2', None , '4.4.4.4',]
        self(y):           ["router-id 1.1.1.1", "router-id 2.2.2.2", "router-id 256.256.256.256", "router-id 4.4.4.4",]        
        intersection_keys: {'1.1.1.1', '4.4.4.4',}
        ↓
        out              : ["router-id 1.1.1.1",    None,                   None, "router-id 4.4.4.4",] 
        '''

        matches_target, err_target = self.matches_to_pattern(ptn)
        matches_filter, err_filter = filter.matches_to_pattern(ptn)
        
        if err_target != []: pass
        if err_filter != []: pass
        
        intersection_keys = {x for x in exclude_element(set(matches_target) & set(matches_filter), None)}

        out = []
        for x, y in zip(matches_target, self):
            if x == None:        # 
                out.append(None) # マッチしなかった要素に対してはNoneを設定
            else:
                for s in intersection_keys:
                    found = False
                    if s == x:
                        out.append(y); found = True
                        break;
                if not found:
                    out.append(None)
        
        return CommandList(out)


    def compare_commandlines(self, filter: 'CommandList', \
                             ptn: int = 1) \
                             -> ('CommandList', 'CommandList'):
        '''インスタンス変数(リスト)を入力されたコマンドリストとパターン内容で比較し、差分(前者－後者)を出力する
        引数:
        filter ：比較対象が設定されたリスト('CommandList'型)
        ptn : 比較対象
              1 : ipv4address
              2 : ipv4network
        filter : 検索処理用の正規表現パターン
        戻り値:
        1. 差分コマンド
        2. エラーが検出されたコマンド

        処理概要
        入力
        self:   ["router-id 1.1.1.1", "router-id 2.2.2.2", "router-id 256.256.256.256", "router-id 4.4.4.4",]
        filter: ["ip address 1.1.1.1", "ip address 999.999.999.999", "ip address 4.4.4.4",]

        Step1 はextract_ip_matched_lineと同様

        Step2 - キー項目の差集合を取り、Noneの要素を削除
        diff_keys     : {'2.2.2.2',}

        Step3: 条件にマッチしたコマンドを抽出、マッチしなかった要素に対してはNoneを設定
        matches_target(x): ['1.1.1.1', '2.2.2.2', None , '4.4.4.4',]
        self(y):           ["router-id 1.1.1.1", "router-id 2.2.2.2", "router-id 256.256.256.256", "router-id 4.4.4.4",]        
        diff_keys        : {'2.2.2.2',}
        ↓
        out              : [None,                "router-id 2.2.2.2" , None,                        None,]
        '''

        matches_target, target_err = self.matches_to_pattern(ptn)
        matches_filter, _ = filter.matches_to_pattern(ptn)

        diff_keys = {x for x in exclude_element(set(matches_target) - set(matches_filter), None)}

        out = []
        for x, y in zip(matches_target, self):
            if x == None:        # 
                out.append(None) # マッチしなかった要素に対してはNoneを設定
            else:
                found = False
                for s in diff_keys:
                    if s == x:
                        out.append(y); found = True
                        break;
                if not found:
                    out.append(None) # マッチしなかった要素に対してはNoneを設定
                
        return CommandList(out), CommandList(target_err)


    def calculate_networks(self)-> (list, list):
        '''IPアドレスとサブネットマスクよりネットワークアドレスを求め結果を返す(ipaddress型)
        引数:
        なし
        戻り値:
        1. インスタンスが保持するリストの各要素からネットワークアドレスを正規表現パターンの内容で抽出、
           ネットワークのhost bit部分に0マスクを施したうえでipnetworks型のリストを作成し返す
           結果が得られない場合はNoneを詰める
        2. マッチする要素が無い場合の元コマンドが格納されたリスト
        例:
        入力(commands) : 
         ["ip address 99.99.16.9/28", "ip address 99.99.16.10/28", "ip address 99.99.16.73/28", "ip address 99.99.16.74/28",]
        戻り値(networks) :
         ['99.99.16.0/28', '99.99.16.0/28', '99.99.16.64/28', '99.99.16.64/28', ]
        戻り値(err_out) : 
         []
        '''
        networks = []; err_out = []
        
        for line in self:
            r = extract_ipv4network(line, strict=False)              
            if r == ():
                networks.append(None) 
                err_out.append("検索エラー" + ":" + line)
            else:
                if r[0]["error"] == None:
                    networks.append(r[0]["ipaddr"])
                else:
                    networks.append(None)
                    err_out.append(r[0]["error"] + ":" + line)    

        return networks, err_out



class CommandLevelList(CommandList):
    '''
    CommandListクラスを継承(is-a)し、加えてコマンド列に対応するレベル情報(levels)および
    処理対象レベルをインスタンス変数に持つクラス
    '''
    def __init__(self, data: list, levels: list, lv: str = "0") -> None:
        '''インスタンス初期化 
        引数
        data   : コマンド列(list)
        levels : dataの各要素のレベルから成るリスト
        lv     : 処理対象レベル(デフォルト:"0")
        戻り値:
        なし
        '''
        super().__init__(data)
        
        if levels is not None:
            if not isinstance(levels, list):
                raise TypeError('{} is not supported'.format(type(levels)))
                
        if len(data) != len(levels):
            raise ValueError('dataとlevelsの長さが異なります')
        
        self.levels = levels; self.lv = lv


    def __iter__(self):
        ''' dataの各要素を返すイテレータ, 親クラス継承
        用例
        >>> for cmd in commandlevellist:
        ...     print(cmd)
        '''
        return super().__iter__()


    def iter(self):
        ''' dataとlevelsの対応する(同一indexを持つ)各要素をタプルにして返すイテレータ
        用例
        >>> for cmd, level in commandlevellist.iter():
        ...     print(cmd, level)
        '''
        return Tuple_Iterator(self.data, self.levels)
    

    def renew_level(self, lv = "1"):
        ''' 処理対象のレベルを更新する
        入力(str) : lv (指定lv情報)
        戻り値 : 自levelsインスタンス内各要素の"level"、およびlv情報について指定された値に書き換えたもの

        例: 入力がlv = "1"の場合
        levels  = [{"level":"1",..}, {"level":"2",..}, {"level":"2",..}, {"level":"1",..},]
        data    = ["cmd1",            "cmd2",           "cmd3",           "cmd4",]
        lv      = "2"
            ↓
        戻り値
        levels  = [{"level":"1",..}, {"level":"1",..}, {"level":"1",..}, {"level":"1",..},] # 書き換え
        data    = ["cmd1",            "cmd2",           "cmd3",           "cmd4",]          # 変更なし
        lv      = "1"                                                                       # 書き換え
        '''

        levels_out = []
        for level in self.levels:
            level_new = level.copy()
            level_new["level"] = lv
            levels_out.append(level_new)

        return CommandLevelList(self.data, levels_out, lv = lv)


    def insert_empty_string(self)-> 'CommandLevelList':
        '''空文字を挿入する
        引数:なし
        戻り値: 前後のコマンド要素でレベルが前のコマンドと比較し下降するとき("2"⇒"1")、
        およびコマンド最終行に空文字("")を挿入し、結果をCommandLevelListインスタンスとして返す。
        例: 入力
        levels : [{"level":"1",..},{"level":"2",..},{"level":"2",..},                 {"level":"1",..},{"level":"2",..},                 ]
        data   : ["cmd1",           "cmd2",          "cmd3",                           "cmd4",          "cmd5",                          ]
           ↓  
        戻り値                                                             (挿入)                                             (挿入)  
        levels : [{"level":"1",..},{"level":"2",..},{"level":"2",..},{"level":"0",..},{"level":"1",..},{"level":"2",..},{"level":"0",..},]
        data   : ["cmd1",           "cmd2",          "cmd3",          "",              "cmd4",          "cmd5",          "",             ]

        '''
        
        levels = self.levels
        cmds = []; levels_new = []
        
        if self.data == []: return CommandLevelList([], [])
        
        for x, i in zip(self, range(len(levels))):
        
            if i == 0:
                cmds.append(x)
                levels_new.append(levels[i])
            else:
                if ((levels[i-1:i+1][0]["level"], levels[i-1:i+1][1]["level"]) == ("2",   "1")) or \
                   ((levels[i-1:i+1][0]["level"], levels[i-1:i+1][1]["level"]) == ("2.1", "1")) or \
                   ((levels[i-1:i+1][0]["level"], levels[i-1:i+1][1]["level"]) == ("2.2", "1")):

                    cmds.append(""); cmds.append(x)
                    levels_new.append({"level": "0", }); levels_new.append(levels[i])
                else:
                    cmds.append(x)
                    levels_new.append(levels[i])
        
        cmds.append(""); levels_new.append({"level": "0", })
        
        return CommandLevelList(cmds, levels_new)


    def specify_commandlevellist(self, target_level: str = "1")-> 'CommandLevelList':
        '''
        自インスタンスのレベル情報(self.lv)と合致する要素を取り出し、CommandLevelListとして返す
        引数:target_level - 指定レベル("1"/"2"/"2.1"/"2.2")(※現状未使用)
        戻り値: 取り出されたCommandLevelList
        '''

        return CommandLevelList([cmd for cmd, level in self.iter() if level["level"] == self.lv],
                                [level for cmd, level in self.iter() if level["level"] == self.lv])
    

    def extract_ip_matched_line(self, filter: 'CommandLevelList', \
                                ptn: int = 1)-> 'CommandLevelList':
        '''target側/filter側コマンドそれぞれ指定されたレベルと合致するコマンド要素をipaddress形式で取り出し、
        CommandLevelクラスの同名メソッドを起動
        引数:flv, tlv : 比較するコマンドレベル("1"/"2"/"2.1"/"2.2")
        出力CommandListのdataにNoneの要素があれば、対応するlevel情報と共に除去し返す
        '''
        cll = self.specify_commandlevellist()
        rtn = super(CommandLevelList, cll).extract_ip_matched_line(filter.specify_commandlevellist(), \
                                                                 ptn = ptn)
        return CommandLevelList([cmd for cmd in rtn.data if cmd != None], \
                                [lv for cmd, lv in zip(rtn.data, self.levels) if cmd != None])


    def compare_commandlines(self, filter: 'CommandLevelList', ptn: int = 1) \
                             -> ('CommandLevelList', 'CommandLevelList'):
        '''target側/filter側コマンドそれぞれ指定されたレベルと合致するコマンド要素を取り出し、
        CommandLevelクラスの同名メソッドを起動し差分(前者－後者)を出力する
        出力CommandListのdataにNoneの要素があれば、対応するlevel情報と共に除去し返す

        エラー検出されたコマンドの戻り値から、CommandlevelListとしてのエラーインスタンスを編集し返す
        err.data: [None, None, None, ("検索エラー:", "130 permit ip 103.103.183.0 0.0.255.255 any"),]
         ↓
        err_out : [                   "検索エラー:130 permit ip 103.103.183.0 0.0.255.255 any",]
         
        levelsについてはerr.dataがNone以外の要素のindexに対応する情報を編集し返す

        備考
        self.levelsの各要素については、key='level'の値がself.lvの値の要素のみ抽出する
         (levelsに対する「specify_commandlevellist」相当の手続き)
        例：
        self.levels = [
                        {'level': '1', ...}, 
                        {'level': '2', ...},
                        {'level': '2', ...},
                        {'level': '2', ...},
                      ]
        self.lv = '2'
            ↓
        new_levels  = [         
                        {'level': '2', ...},
                        {'level': '2', ...},
                        {'level': '2', ...},
                      ]
        '''
        cll = self.specify_commandlevellist()
        rtn, err = super(CommandLevelList, cll).compare_commandlines(filter.specify_commandlevellist(), \
                                                                 ptn = ptn)

        err_out = []; levels_out = []
        new_levels = []

        for lv in self.levels:
            if lv['level'] == self.lv:    
                new_levels.append(lv)
            
        for e, lv in zip(err.data, new_levels):
            if e != None:
                err_out.append(e[0] + e[1]) # コマンド文字列とエラーメッセージをstr結合

                lv_new = lv.copy()
                lv_new["span-list"] = self.renew_span_range(lv_new["span-list"], len(e[0])) 
                levels_out.append(lv_new) 

        return CommandLevelList([cmd for cmd in rtn.data if cmd != None], \
                                [lv for cmd, lv in zip(rtn.data, self.levels) if cmd != None]), \
               CommandLevelList(err_out, levels_out)


    def add_networkinfo(self)-> 'CommandLevelList':
        '''レベル指定要素を取り出し、patternで特定されたネットワーク情報をコマンド行頭に付加した情報と、
        自インスタンスのlevels情報内のspan情報を更新した情報を返す
        '''
        
        cll = self.specify_commandlevellist() # レベル指定要素の取り出し(CommandLevelList型)
        networks, err_out = cll.calculate_networks()  # ipaddressのリストとstrのリスト

        L = []
        levels_new = []

        for network, line, level in zip(networks, cll.data, cll.levels):
            level_new = level.copy()
            if network != None:
                L.append(network + " : " + line )
                if "span-list" in level:
                    level_new["span-list"] = self.renew_span_range(level["span-list"], len(str(network) + " : "))
                levels_new.append(level_new)
            else:
                L.append("エラー : " + line )
                if "span-list" in level:
                    level_new["span-list"] = self.renew_span_range(level["span-list"], len("エラー : "))
                levels_new.append(level_new)

        return CommandLevelList(L, levels_new, lv = self.lv)


    def search_command_info(self, ptn: int, pattern: str or 're.Pattern' = "", strict:bool = True)-> 'CommandLevelList':
        '''self.data(コマンド列)に含まれる文字列を入力された比較対象またはパターンを用いget_span_infoメソッドで検索し、
        求めたspan情報をself.levels情報に挿入し新規インスタンスとして返す。
        self.dataの内容は同じものを設定する
        挿入元・先のspan情報の「重複」「重なり」は本メソッドでは意識せず、insert_spanメソッドで一括して取り扱う
        引数:
        ptn : 比較対象
              1 : ipv4address
              2 : ipv4network
              3 : 任意文字列(patternで検索パターンを指定)
        pattern: 検索処理用の正規表現パターン(ptn=3の場合)
        戻り値:
        結果が格納されたCommandLevelList
 
        例:
        入力(self.data) : 
         ["ip address 192.168.16.0/30", 
          "ip address 192.168.17.0/30",]
        入力(self.levels) :
         [{"level": "2", "line_number":10, 
           "span-list":[{"atype":"INFO", "error":None, "span":(0,10)},],
          {"level": "2", "line_number":11, 
           "span-list":[{"atype":"INFO", "error":None, "span":(0,10)},],
        get_span_infoメソッドで得た情報
         [(
           {'atype': 'A4', 'error': None, 'span': (11, 22)}, 
           {'atype': 'M4', 'error': None, 'span': (22, 23)}, 
           {'atype': 'M4', 'error': None, 'span': (23, 25)},
          ),( 
           {'atype': 'A4', 'error': None, 'span': (11, 22)}, 
           {'atype': 'M4', 'error': None, 'span': (22, 23)}, 
           {'atype': 'M4', 'error': None, 'span': (23, 25)},
          )]

        戻り値(data) : 同じものを返す 
        戻り値(levels) : get_span_infoメソッドで得た情報を挿入--
         [
          {"level": "2", "line_number":10,
           "span-list":[{"atype":"INFO", "error":None, "span": (0,10)},
                        {'atype': 'A4', 'error': None, 'span': (11, 22)},     # 挿入
                        {'atype': 'M4', 'error': None, 'span': (22, 23)},     # 挿入
                        {'atype': 'M4', 'error': None, 'span': (23, 25)},],}, # 挿入
          {"level": "2", "line_number":11,
           "span-list":[{"atype":"INFO", "error":None, "span": (0,10)},
                        {'atype': 'A4', 'error': None, 'span': (11, 22)},     # 挿入
                        {'atype': 'M4', 'error': None, 'span': (22, 23)},     # 挿入
                        {'atype': 'M4', 'error': None, 'span': (23, 25)},],}, # 挿入
         ]         
        '''
        
        levels_new = []
        for item, lv in zip(self.get_span_info(ptn, pattern, strict), self.levels): # 各コマンド毎

            d = {"level": lv["level"]} # Levels_newの要素である辞書の初期化

            if "line_number" in lv:
                d["line_number"] = lv["line_number"]

            if "span-list" in lv:           
                # 各itemより"span"情報を取り出し、selfのlevelsの各要素(辞書)の"span-list"に付加する
                L = lv["span-list"].copy() # 新しいspan_listの各要素「※span情報」の初期化
                for i in range(len(item)): # CommandLevelList要素の各spaninfo情報でループ
                    L = self.insert_span(item[i], L)
                d["span-list"] = L

            levels_new.append(d)
    
        return CommandLevelList(self.data, levels_new)


    def to_cln(self)-> 'CommandListNetwork':
        ''' CommandLevelListからCommandListNetworkへの型変換メソッド'''
        return CommandListNetwork(self.specify_commandlevellist())


    def to_cla(self)-> 'CommandListAddress':
        ''' CommandLevelListからCommandListAddressへの型変換メソッド'''
        return CommandListAddress(self.specify_commandlevellist())


    def to_cls(self, pattern: str)-> 'CommandListString':
        ''' CommandLevelListからCommandListStringへの型変換メソッド'''
        return CommandListString(self.specify_commandlevellist(), pattern)

   
    def extend(self, cll2: 'CommandLevelList')-> 'CommandLevelList':
        ''' CommandLevelListクラスのインスタンスを伸長する
        動作内容
        -self.dataの末尾にcll2.dataの全アイテムを、self.levelsの末尾にcll2.levelsの全アイテムを追加
        -lvの値はselfの値を引き継ぐ
        '''
        if not isinstance(cll2, CommandLevelList):
            raise TypeError('{} is not supported'.format(type(cll2)))
        self.data.extend(cll2.data); self.levels.extend(cll2.levels)
        return CommandLevelList(self.data, self.levels, lv = self.lv)


    def make_hierachy(self, *args, ptn=1)-> 'CommandLevelList':
        ''' patternでマッチした情報要素を用い階層構造を作成し返す
        ptn=1,2の二種類の構造をサポートする(詳細は下記)
        ptn=1,2に共通の制約事項として、マッチに用いる情報要素は1つに限定する
        
        入力(ptn=1)
        args[0]: CommandLevelListインスタンス
        args[1]: マッチ要素検索用パターン
        入力(ptn=2)
        args[0]: CommandLevelListインスタンス1
        args[1]: マッチ要素検索用パターン1
        args[2]: CommandLevelListインスタンス2
        args[3]: マッチ要素検索用パターン2
        
        - ptn=1
        
        入力例：
        ●ip access-group設定(ルート情報)
        ip access-group vSAMPLE-TEST-NER-IN-ACL in
        ip access-group vSAMPLE-TEST-NER-IN-ACL in
        ip access-group vSAMPLE-TEST1-NER-IN-ACL in
        ip access-group vSAMPLE-TEST1-NER-IN-ACL in
        ●ACL設定(第1階層の元情報)
        ip access-list vSAMPLE-TEST-NER-IN-ACL
        10 permit ip 100.100.0.0 0.0.0.3 any
        10 permit ip 100.100.0.4 0.0.0.3 any
        ip access-list vSAMPLE-TEST1-NER-IN-ACL
        20 permit ip 100.100.1.0 0.0.0.3 any
        20 permit ip 100.100.1.4 0.0.0.3 any
        ip access-list vSAMPLE-TEST1-NER-IN-ACL
        20 permit ip 100.100.9.0 0.0.0.3 any
        20 permit ip 100.100.9.4 0.0.0.3 any
 
        出力例:ルート情報およびそのリンク情報「vSAMPLE-TEST-NER-IN-ACL」で辿った先の配下データを出力
        ●階層構造の表示
        凡例:
        ルート階層
        └第1階層
        ip access-group vSAMPLE-TEST-NER-IN-ACL in
        ├10 permit ip 100.100.0.0 0.0.0.3 any
        └10 permit ip 100.100.0.4 0.0.0.3 any
        ip access-group vSAMPLE-TEST1-NER-IN-ACL in
        ├10 permit ip 100.100.1.0 0.0.0.3 any
        └10 permit ip 100.100.1.4 0.0.0.3 any
      
        制約事項：
        ルート情報に同一のリンク情報(上記例でvSAMPLE-TEST-NER-IN-ACL)が重複して現れる場合は、
        最上位に現れる情報のみをルート階層データに反映
        第1階層の元情報(今の例ではACL設定)に同一のリンク情報が重複して現れる場合は、
        階層データには最も上に位置する情報のみ反映
        リンクされる各要素(上記例で10 permit ...)はすべて階層データに反映

        - ptn=2

        入力例：
        ●BGP設定(Direct)(ルート情報)
        router bgp 65111
        redistribute direct route-map vSAMPLE-001-TEST-DIRECT-TO-BGP-MAP
        redistribute direct route-map vSAMPLE-002-TEST-DIRECT-TO-BGP-MAP
        
        ●DirectルートをBGPに再配送するためのルートマップ(第1,2階層の元情報)
        route-map vSAMPLE-001-TEST-DIRECT-TO-BGP-MAP permit 10
        match ip address prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL
        match ip address prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL
        route-map vSAMPLE-002-TEST-DIRECT-TO-BGP-MAP permit 10
        match ip address prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL
            
        ●DirectルートをBGPに再配送するための経路フィルタ(第3階層の元情報)
        ip prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL seq 10 permit 222.222.20.0/28 le 32
        ip prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL seq 20 permit 100.100.2.0/30 le 32
        ip prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL seq 10 permit 222.222.20.64/28 le 32
 
        出力例:ルート情報およびそのリンク情報「vSAMPLE-001-TEST-DIRECT-TO-BGP-MAP」で辿った先の配下データ、
        さらに存在するリンク情報「vSAMPLE-001-TEST-DIRECT-TO-BGP-PL」で辿った先の配下データを出力

        ●階層構造の表示
        凡例:
        ルート階層
        └第1階層
         └第2階層
           └第3階層
        redistribute direct route-map vSAMPLE-001-TEST-DIRECT-TO-BGP-MAP
        └route-map vSAMPLE-001-TEST-DIRECT-TO-BGP-MAP permit 10
         ├match ip address prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL
         │├ip prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL seq 10 permit 222.222.20.0/28 le 32
         │└ip prefix-list vSAMPLE-001-TEST-DIRECT-TO-BGP-PL seq 20 permit 100.100.2.0/30 le 32
         └match ip address prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL
           └ip prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL seq 10 permit 222.222.20.64/28 le 32 
        redistribute direct route-map vSAMPLE-002-TEST-DIRECT-TO-BGP-MAP
        └route-map vSAMPLE-002-TEST-DIRECT-TO-BGP-MAP permit 10
         └match ip address prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL
           └ip prefix-list vSAMPLE-002-TEST-DIRECT-TO-BGP-PL seq 10 permit 222.222.20.64/28 le 32

        内部変数(two_dim_data1/two_dim_levels)-データ構造はmake_two_dim_listのコメント参照
        two_dim_data1の例
        例1(ptn=1のケース)
        [
         ['ip access-group TEST1', '10 permit ip ...', '20 permit ip ...',],
         ['ip access-group TEST2', '10 permit ip ...', '20 permit ip ...',],
        ]
        例2(ptn=2のケース)
        [
         ['route-map vSAMPLE-001...', 'match ip address prefix-list ...', 'match ip address prefix-list ...',],
         ['route-map vSAMPLE-002...', 'match ip address prefix-list ...',],
        ] 

        制約事項：               
        ルート情報redistribute direct route-map(上記例のvSAMPLE-001-...)にリンクするコマンドが複数重複して
        存在する場合は(例:route-map vSAMPLE-001-TEST-DIRECT-TO-BGP-MAPが複数存在)、最も上に位置する行のみリンク反映
        (キー以外の可変部分、例えばpermit xxの部分が異なる場合も同様に最も上に位置する行のみリンク反映)
        第2階層目の情報要素(上記例でmatch ip address prefix-list)は無条件で
        (すなわち以降のリンクパターンに合致するものがあってもなくても)階層データに反映
        (ここは単数でも複数の情報要素であってもリンク反映)

        その他:
        罫線素片の標準出力上の表示が一文字分に満たないため次の文字が重なって表示されてしまう事象回避のため、
        罫線素片とその次の文字の間にASCII空白を挿入する
        args[1]のインスタンス確認で比較対象に使用するre.PatternクラスはPython3.7以降で有効
        
        罫線素片の挿入時、span情報のstart/stopインデックスが変わるため、挿入のたびにspanlistの更新を行う
        '''

        char_mid  = BOX_DRAWINGS_LIGHT_VERTICAL_AND_RIGHT # "├"(細線素片左)
        char_last = BOX_DRAWINGS_LIGHT_UP_AND_RIGHT       # "└"(細線素片左下)
        char_cont = BOX_DRAWINGS_LIGHT_VERTICAL           # "│"(縦細線素片)
        s         = SPACE                                 # " "
        ss        = s * 2                                 # "    "

        # 罫線素片とその次の文字の間に挿入する文字定義(ASCIIの空白)
        b         = SPACE                                 # " "


        if len(args) < 2: raise ValueError('パラメータ数が不足しています')

        major = sys.version_info.major; minor = sys.version_info.minor

        if not isinstance(args[0], CommandLevelList):
            raise TypeError('{} is not supported'.format(type(args[0])))

        if major == 3 and minor >= 7:  # Python 3.7以降を想定（Python 4がないこと前提）
            if not isinstance(args[1], re.Pattern) or isinstance(args[1], str):
                raise TypeError('{} is not supported'.format(type(args[1])))
                
        two_dim_data1, two_dim_levels = args[0].make_two_dim_list()
        pattern1 = args[1]
                
        if ptn == 2:
            if len(args) < 4: raise ValueError('パラメータ数が不足しています')

            if not isinstance(args[2], CommandLevelList):
                raise TypeError('{} is not supported'.format(type(args[2])))
            
            if major == 3 and minor >= 7:
                if not isinstance(args[3], re.Pattern) or isinstance(args[3], str):
                    raise TypeError('{} is not supported'.format(type(args[3])))

            cll_pl   = args[2]
            pattern2 = args[3]
                
        out, levels_out, done = [], [], []
        done1 = [] # 2段目要素の重複チェック用

        span_list = self.get_span_info(ptn = 3, pattern = pattern1)

        for (line, level), sp in zip(self.iter(), span_list):
            if line in done: continue  # 一度出力したデータは出力しない
            else: done.append(line)
            
            if sp != (): 
                # (例:ptn=1) ip access-group vSAMPLE-TEST-...
                # (例:ptn=2) redistribute static route-map vSAMPLE-001-TEST-...
                out.append(line)

                level["span-list"] = self.insert_span(sp[0], level["span-list"]) # 最初のspan要素のみを挿入
                levels_out.append(level) # 追加

                for i in range(len(two_dim_data1)):
                        
                    m1 = re.search(pattern1, two_dim_data1[i][0])
                    if m1 is None: continue  # 次のfor処理へ
                    if sp[0]["key"] != m1.group(1): continue
                    if m1.group(1) in done1: continue # ptn=1,2いずれも同じキー項目が再度出現した場合は2つ目以降処理しない
                    else: done1.append(m1.group(1))

                    # span情報の作成・挿入(二次元リスト側-本メソッドが作る階層構造データではないほう-を更新)
                    span1 = {"atype":"KEY", "error":None, "span":m1.span(1), "key":m1.group(1),} 
                    two_dim_levels[i][0]["span-list"] = self.insert_span(span1, two_dim_levels[i][0]["span-list"])

                    if ptn == 1:

                        if len(two_dim_data1[i]) > 2:
                            for j in range(1, len(two_dim_data1[i])): # 2層目の1番目から最後までの要素で反復

                                d = two_dim_levels[i][j].copy() # 辞書の複写    

                                if j != len(two_dim_data1[i])-1:
                                    # (例) ├ 10 permit ip ...
                                    out.append(char_mid + b + two_dim_data1[i][j])
                                    d["span-list"] = self.renew_span_range(d["span-list"], len(char_mid + b))
                                else:
                                    # (例) └ 20 permit ip ...
                                    out.append(char_last + b + two_dim_data1[i][-1])
                                    d["span-list"] = self.renew_span_range(d["span-list"], len(char_last + b))
                               
                                levels_out.append(d)

                        break # 一つ内側のfor反復を抜け最も外側のfor反復に戻る(次のルート情報「ip access group...」の処理を実行) 

                    if ptn == 2:
                
                        # (例) └ route-map vSAMPLE-001-TEST-LB-STATIC-TO-BGP-MAP...
                        out.append(char_last + b + two_dim_data1[i][0])

                        d = two_dim_levels[i][0].copy() 
                        d["span-list"] = self.renew_span_range(d["span-list"], len(char_last + b))
                        levels_out.append(d)
                     
                        if len(two_dim_data1[i]) == 1: continue
                            
                        # 2層目の1番目以降、最後までの要素をスライスし、m2_workリストに積む
                        # (match ip address...の要素列)
                        m2_work = two_dim_data1[i][1:]
                        m2_work_level = two_dim_levels[i][1:]
                            
                        if len(m2_work) == 0: continue

                        def proceed_last_block(end=False)-> None:
                            ''' 最終段(第3段目)の作成処理
                            
                            入力: end-True/False:第2段目の最終要素/最終以外
                                 (pattern2, cll_plについては主処理側の変数を関数内から参照)
                            戻り値: 無し

                            処理内容:
                            1. 第2段目(例 match ip address...要素列)の要素のキー情報(.*?-TO-BGP-PL)と
                            一致するものを第3段目の要素として抜き出し、ワーク用リストに積む
                            2. 第2と第3段目のリンク結合を行う
                            
                            第2段目の最終要素にリンク結合させる処理と、最終以外の要素にリンクさせる処理(別ルートにおける類似内容)を共通化する
                            '''                   

                            # ワーク域初期化(list) - いずれもm3のキャプチャ要素がNone以外、かつm2のキャプチャ結果と等しい場合に設定
                            m3_work = [] # 第3段目コマンド列格納用
                            m3_list = [] # pattern2を使用したキャプチャ結果のMatch格納用
                            m3_work_level = [] # コマンド列に対応するLevels要素格納用

                            def set_span3(length, end=False)-> None:
                                ''' 最終段(第3段目)のspan情報処理
                            
                                入力: end-True/False(bool): 最終段(第3段目)における最終要素/最終以外
                                      len(int)            : spanの延長数
                                戻り値: 無し
                            
                                処理内容:
                                第3段目(例 ip prefix-list...要素列)について、階層表示に積む要素のspan情報を更新し、
                                合わせて、元要素(二次元情報側=>本メソッドの階層表示ではない方)のspan情報も更新する   
                                '''
                                if end != True:
                                    span3 = m3_list[k]; d = m3_work_level[k].copy() 
                                else:
                                    span3 = m3_list[-1]; d = m3_work_level[-1].copy()
                                
                                _ = self.insert_span(span3, d["span-list"])
                                d["span-list"] = self.renew_span_range(_, length)
                                levels_out.append(d)

                                # ip prefix-list...の元要素                      
                                if end != True:
                                    m3_work_level[k]["span-list"] = self.insert_span(span3, m3_work_level[k]["span-list"])
                                else:
                                    m3_work_level[-1]["span-list"] = self.insert_span(span3, m3_work_level[-1]["span-list"])

                            span3_list = CommandList(cll_pl.data).get_span_info(ptn = 3, pattern = pattern2)
                            for (cmd, lv), sp3 in zip(cll_pl.iter(), span3_list):
                                if sp3 != ():
                                    if sp3[0]["key"] == sp2[0]["key"]:
                                        m3_work.append(cmd); m3_list.append(sp3[0]); m3_work_level.append(lv)

                            if m3_work != []:
                                if end != True:
                                    # 最終段が存在する(m3_work != [])ため、リンク元(match ip address...)のspan情報を挿入(二次元情報側)
                                    # コマンド自体はメイン処理で追加済み(out.append(...))                           
                                    m2_work_level[j]["span-list"] = self.insert_span(sp3[0], m2_work_level[j]["span-list"])

                                    for k in range(len(m3_work)):
                                        if k != len(m3_work)-1:
                                            # (例) │ ├ ip prefix-list vSAMPLE-001-...
                                            out.append(s + char_cont + b + char_mid + b + m3_work[k]) # 「左端から」の相対位置分を加算
                                            set_span3(len(s + char_cont + b + char_mid + b), end=False) 
                                        else:
                                            # (例) │ └ ip prefix-list vSAMPLE-001-...
                                            out.append(s + char_cont + b + char_last + b + m3_work[-1])
                                            set_span3(len(s + char_cont + b + char_last + b), end=True) 

                                else:
                                    m2_work_level[-1]["span-list"] = self.insert_span(sp3[0], m2_work_level[-1]["span-list"])

                                    for k in range(len(m3_work)):
                                        if k != len(m3_work)-1:                        
                                            # (例)  ├ ip prefix-list vSAMPLE-001-...
                                            out.append(ss + char_mid + b + m3_work[k])
                                            set_span3(len(ss + char_mid + b), end=False) 
                                        else:
                                            # (例) └ ip prefix-list vSAMPLE-001-...
                                            out.append(ss + char_last + b + m3_work[-1])
                                            set_span3(len(ss + char_last + b), end=True) 

                        span2_list = CommandList(m2_work).get_span_info(ptn = 3, pattern = pattern2)
                        for j, sp2 in zip(range(len(m2_work)), span2_list):
                            d = m2_work_level[j].copy()

                            if j != len(m2_work)-1: # 第2段目の最終要素かどうかの判定
                                # (例) ├ match ip address prefix-list vSAMPLE-001-...
                                out.append(s + char_mid + b + m2_work[j])
                                d["span-list"] = self.renew_span_range(d["span-list"], len(s + char_mid + b))
                            else:
                                # (例) └ match ip address prefix-list vSAMPLE-001-TEST-...
                                out.append(s + char_last + b + m2_work[j])
                                d["span-list"] = self.renew_span_range(d["span-list"], len(s + char_last + b))
                            levels_out.append(d)

                            if sp2 != ():                                 
                                # match ip addressに対応する(直前で追加した)levels要素にm2.span情報をinsert                                
                                # 既にlevels_outに追加しspanレンジも更新しているため、前回の更新分を個別に加算
                                d = levels_out[-1]

                                if j != len(m2_work)-1:                                
                                    sp2[0]["span"] = tuple((list(sp2[0]["span"])[0]+len(s + char_mid + b),
                                                           (list(sp2[0]["span"])[1]+len(s + char_mid + b))
                                                          ))
                                else:
                                    sp2[0]["span"] = tuple((list(sp2[0]["span"])[0]+len(s + char_last + b),
                                                           (list(sp2[0]["span"])[1]+len(s + char_last + b))
                                                          ))
                                d["span-list"] = self.insert_span(sp2[0], d["span-list"])
                                levels_out[-1] = d

                                if j != len(m2_work)-1:
                                    # 以下"ip prefix-list..のコマンド行処理のための共通関数
                                    #  ├ match ip address prefix-list vSAMPLE-002-...
                                    #  │ ├ ip prefix-list vSAMPLE-002-... 
                                    #   ...
                                    proceed_last_block(False)   
                                else:
                                    # 以下"ip prefix-list..のコマンド行処理のための共通関数
                                    #  └ match ip address prefix-list vSAMPLE-002-...
                                    #    ├ ip prefix-list vSAMPLE-002-... 
                                    #   ...
                                    proceed_last_block(True)  
                                        
        # levelsのすべての要素を"level":"1"に設定(insert_empty_stringで改行設定をさせない)
        return CommandLevelList(CommandLevelList(out, levels_out).renew_level(lv = "1").data, \
                                CommandLevelList(out, levels_out).renew_level(lv = "1").levels, lv = "1")


    def make_two_dim_list(self)-> (list, list):
        ''' CommandLevelListインスタンスのdata,Level変数より二次元リストを作成する
        処理概要
        data変数に関し、サブリストをリスト内部に保持し、そのサブリストの内容として、
        ・levels="1"に対応するコマンドを0番目の要素、
        ・後続にlevels="1"以外のコマンドが存在すれば、1番目以降の要素
        ・後続がlevels="1"のコマンドの場合は、新たなサブリストを作成し0番目の要素
        となるようなリストを作成し返す
        levelsについても同様なリストを作成し返す

        例
        self.data = ["cmd1-1", "cmd1-2", "cmd1-3", "cmd2-1", "cmd3-1", "cmd3-2"]
        self.levels = [{level:"1",...}, {level:"2.1",...}, {level:"2.1",...}, {level:"1",...}, {level:"1",...}, {level:"2",...}]
        の場合の出力
        out = [
               ["cmd1-1", "cmd1-2", "cmd1-3"],
               ["cmd2-1"],
               ["cmd3-1", "cmd3-2"]
              ]
        levels_out = [
               [{"level":"1",..}, {"level":"2.1",..}, {"level":"2.1",..},],
               [{"level":"1",..},],
               [{"level":"1",..}, {"level":"2",..},]
              ]
        注意事項
        返されるリストは元リストのコピーではなく参照(二次元リストの内容を変更すると元リストの内容も同様に変更される)
        '''
        pos = []
        if self.data == []: return [], []
        
        # "level":"1"に対応する要素のindex値を集めリスト化-上記の例のケースではpos = [0, 3, 4]
        for i in range(len(self.levels)):
            if self.levels[i]["level"] == "1":
                pos.append(i)
                
        out = []; levels_out = []

        for i in range(len(pos)):
            
            sublist, levels_sublist = [], []
            sublist.append(self.data[pos[i]]); levels_sublist.append(self.levels[pos[i]])

            last = pos[i+1] if i != len(pos)-1 else len(self.data)
           
            for j in range(pos[i]+1, last):
                sublist.append(self.data[j]); levels_sublist.append(self.levels[j])                                 
            
            out.append(sublist); levels_out.append(levels_sublist)
           
        return out, levels_out



    @classmethod
    def check_span(cls, span:dict)-> bool:
        ''' span情報につき以下のチェックを実施する
        引数: span(dict)
        戻り値: True/False
        詳細:以下の確認を実行し、正常ならTrue, 異常ならfalseを返す
        ・span開始位置(start), 終了位置(stop)とも0以上の整数、かつstart <= stopであること
        '''
        start, stop = span["span"]
        return start >= 0 and stop >= 0 and start <= stop  # bool値


    @classmethod
    def check_span_list(cls, span_list:list)-> None:
        ''' span_list情報のチェックを行なう
        引数: span_list(list)
        戻り値: 詳細に示すチェックを実施し、結果が正常の場合Noneを返し、異常の場合は例外を発生させる(戻り値無し)
        詳細: 
        各要素ともspan開始位置(start), 終了位置(stop)とも0以上の整数、かつstart <= stopであること
        合わせて前後するspan要素について前のstop位置 <= 次のstart位置であること        
        '''
        for i in range(len(span_list)):
            if "span" not in span_list[i]: 
                # "span"をキーにする要素が存在しない
                raise ValueError('{} does not contain span'.format(span_list[i]))
            if CommandLevelList.check_span(span_list[i]) == False:
                raise ValueError('{} contains value(s) not supported'.format(span_list[i]["span"]))
            if i >= 1:
                if span_list[i]["span"][0] < span_list[i-1]["span"][1]:   # 後spanのstart < 前spanのstopのケースをエラーと扱う
                    raise ValueError('Tuples {} contains value(s) not supported - stop value exceeds start value of next tuple'.format((span_list[i-1]["span"], span_list[i]["span"])))
        return None


    @staticmethod
    def insert_span(span:dict, span_list:list)-> list:
        '''
        span_listに対し指定されたspan情報を挿入し返す。span情報以外の要素は変更しない
        入力:span      - これから挿入しようとするspan情報
             span_list - 挿入される側のspan情報の(辞書の)リスト
        戻り値:挿入が完了したspan_list
        内部情報:exc(list) - span_listのfor反復内の実行要・不要を管理するフラグ(True/False:要/不要)
                            用途 : 二つ以上のspan要素のレンジを含む挿入対象spanを検出した際、listの先読みを行った結果、
                            listの先に存在する要素削除を行った際にFalseの履歴を残し、後の反復実行の際に処理をスキップする
        本メソッドの目的と用途
        正規表現によるキャプチャデータ取得が複数回にわたり実行された場合、前回取得済みのspan(start, stop)情報に対し
        新たに取得したspan情報を加えて保持する必要があり、その操作を本メソッドで実行する
        既存span情報との重なりがある場合は必要な情報操作を実行する
        (重なりがのこったままターミナル出力に使用してしまった場合、重なりの部分に対応する情報の二重出力を引き起こしてしまう)

        実現例を以下に示す
        ケース1(既存span情報との重なり無し、単純追加)
        入力
        span      :{...,  "span":(14,19),...}
        span_list :[{..., "span":(7,11),... },       (単純追加)            {..., "span":(20,23),...},]                        
        戻り値     :[{..., "span":(7,11),... }, {..., "span":(14,19),...}, {..., "span":(20,23),...},]

        ケース2(前の要素との重なり、前に位置する要素を変更)
        ケース3(後の要素との重なり、後に位置する要素を変更)
        入力
        span      :{...,  "span":(14,19),...}
        span_list :[{..., "span":(7,16),... },                            {..., "span":(17,23),...},]                        
        戻り値     :ケース2(stop:16=>14))         (挿入要素は変更しない)        ケース3(start:17=>19)
                   [{..., "span":(7,14),... }, {..., "span":(14,19),...}, {..., "span":(19,23),...},]
                   
        ケース4(挿入するspanレンジが既存要素のレンジを含む場合・・後に位置するspan情報の要素を削除)
        入力
        span      :{...,  "span":(14,23),...}
        span_list :[{..., "span":(7,16),... },                            {..., "span":(17,23),...},]                        
        戻り値     :    stop:16=>14               (挿入要素は変更しない)                (削除)
                  :[{..., "span":(7,14),... }, {..., "span":(14,23),...},                           ]

        ケース5(挿入するspanが既存の最終以外の要素のレンジに含まれる場合・・i-1番目要素のspanレンジ補正)
        入力
        span      :{...,  "span":(2,10),...}
        span_list :[{..., "span":(0,14),... },                                                     {..., "span":(16,26),...},]                        
        戻り値     : 既存要素を削除、前後のspanを作成(挿入要素は変更しない)
                  :[{..., "span":(0,2),... }, {...,  "span":(2,10),...},{..., "span":(10,14),... },{..., "span":(16,26),...},]

        ケース6(挿入するspanが既存の最終要素のレンジと重なる・あるいは含まれる場合・・既存要素を削除しspan追加)
        入力
        span      :      {...,  "span":(64,70),...}
        span_list :[...,                            {..., "span":(50,80),...},]                        
        戻り値     : 既存要素を削除、前後のspanを作成(挿入要素は変更しない)
                  :[..., {...,  "span":(50,64),...},{..., "span":(64,70),... },{..., "span":(70,80),...},]

                          
        備考 : span_listへのspan挿入パターン
        pos
                  1         2         3 
        0123456789012345678901234567890

        span_list(パターン1, i(=0)番目要素の処理)   検証ケース
        ----------------------------------------  -------------
           i
        +------+   +-----+     

        1-1
        +-+                       => ケース5


        span_list(パターン2, i番目要素の処理  )    検証ケース
        ---------------------------------------  -------------
                i
            +------+   +-----+

        2-1
         +-+                      => ケース1

        2-2
          +---+                   => ケース3

        2-3
           +--------+             => ケース4

        2-4
          +--------------+        => ケース7

        2-5            
          +--------------------+  => ケース8                  

        2-6 
            +------+              => ケース9 


        span_list(パターン3, i番目処理で(i-1)の複写を      検証ケース
        ----------------------------------------------  -------------
                          i
            +------+   +-----+

        3-1
             +---+                => ケース5

        3-2
                 +---+            => ケース2

        3-3
                    +-+           => ケース1  

        3-4
                     +---+        => ケース3


        span_list(パターン4, for-i反復終了後の処理))   検証ケース
        ------------------------------------------   ---------
                        last
            +------+   +-----+
        
        4-1
                        +---+     => ケース6

        4-2
                           +---+  => ケース6

        4-3
                              +-+ => ケース9
                     

        span_list(パターン5, i番目i+1番目の連結)    検証ケース
        ---------------------------------------  ------------
               i
          +------+------+

        5-1
         +---------+               => ケース7  

        5-2
         +------------------+      => ケース8       


        span_list(パターン6, 長さ0のspan-そのまま挿入)   検証ケース
        --------------------------------------------  ------------
                    i
          +---+  +------+

        6-1                 
               +                   => ケース1

        6-2                  
                   +               => ケース6

        '''
        out = []; exc = [True]*len(span_list); ins = False; 

        if "span" not in span: return span_list
        if CommandLevelList.check_span(span) == False:
            raise ValueError('{} contains value(s) not supported'.format(span))
        if CommandLevelList.check_span_list(span_list) == None: pass

        for i in range(len(span_list)):
            if exc[i] == False:
                continue              # 次のfor反復へ(ケース7, 8でi番目要素を処理済み)

            out.append(span_list[i].copy()) # 複写渡し(outを変更した場合のspan_listへの影響を排除)

            if span_list[i]["span"][0] <= span["span"][0]:
                # span_listのi番目要素(span_list[i])のstart番号 <= spanのstart番号なら、span_list要素のみ詰める
                #               i   
                # span_list +------+   +-----+     
                # span(例1) +---+               ('='等号の場合)
                # span(例2)    +---+
                # span(例3)      +-------+
                #   ...  
                pass 
               
            else:
                if ins == True:
                    pass
                else:
                    ins = True            
                    out.insert(-1, span)  # span_list[i]の複写の一つ前
                    
                    if i >= 1:
                        if span_list[i-1]["span"][1] <= span["span"][0]:
                            if span["span"][1] <= span_list[i]["span"][0]:
                                # 挿入したspanが一つ前のspan_listと追加したspan_listの間にある場合-単純追加(ケース1)
                                #      i-1        i
                                #   +------+   +-----+
                                #           +-+
                                continue                          
                           
                        elif span["span"][0] < span_list[i-1]["span"][1]:
                            if span["span"][1] <= span_list[i-1]["span"][1]:
                                # 挿入したspanが既存の最終以外の要素のレンジに含まれる場合・・i-1番目要素のspanレンジ補正(ケース5)

                                if span_list[i-1]["span"][0] == span["span"][0]:
                                    if span["span"][1] < span_list[i-1]["span"][1]:
                                        # i-1の要素に対応するoutのstart番号を書き換え
                                        #      i-1        i
                                        #   +------+   +-----+
                                        #   +---+

                                        d = out.pop(-3)     # 前回追加したspan_list[i-1]を取り出し
                                        L = list(d["span"]) 
                                        L[0] = span["span"][1]
                                        d["span"] = tuple(L)
                                        out.insert(-1, d)   # 今回追加したspanとspan_list[i]の間に挿入

                                    elif span["span"][1] == span_list[i-1]["span"][1]:
                                        # i-1の要素に対応するoutの要素を削除(ケース9)
                                        #      i-1        i
                                        #   +------+   +-----+
                                        #   +------+

                                        out.pop(-3)     # 前回追加したspan_list[i-1]を削除

                                else: 
                                    # i-1の要素に対応するoutのstop番号を書き換え
                                    #      i-1        i
                                    #   +------+   +-----+
                                    #   　+--+
                                    L = list(out[-3]["span"]) 
                                    L[1] = span["span"][0]
                                    out[-3]["span"] = tuple(L)
                               
                                    if span["span"][1] < span_list[i-1]["span"][1]:
                                        # i-1の要素のstopが書き換えられているため、新規のspan作成および追加 
                                        d = span_list[i-1].copy()
                                        d["span"] = (span["span"][1], span_list[i-1]["span"][1])
                                        out.insert(-1, d)
                           
                                continue # 次のfor反復へ

                            else:
                                if span_list[i-1]["span"][0] == span["span"][0]:
                                # 挿入したspanと一つ前のspan_listのspanと重なりあり、始点が同じ。
                                #      i-1        i
                                #   +------+   +-----+
                                #   +--------+
                                # または
                                #   +-----------+
                                # ...
                                    out.pop(-3)     # 前回追加したspan_list[i-1]を削除

                                else:
                                    # 挿入したspanと一つ前のspan_listのspanと重なりあるが、含まれてはいない場合の補正(ケース2)
                                    #      i-1        i
                                    #   +------+   +-----+
                                    #      +------+
                                    #
                                    # または  
                                    #      +-----------+
                                    #
                                    # または
                                    #      +-----------------+
                                    #   +--+        <= i-1の要素と置き換え
                                    #                 (iの要素との重なりは現在のif i >= 1:文を抜けた次のif文以降で処理)
                                    # ...                      
                                    L = list(out[-3]["span"])  # outの要素でいうと2つ前の辞書value(タプル)=>リスト
                                    L[1] = span["span"][0] 
                                    out[-3]["span"] = tuple(L) # リストをタプル化し、辞書valueの置き換え

                    if span["span"][1] <= span_list[i]["span"][0]:
                        # 挿入したspanと現在処理中のspan要素のstart位置との重なりがない場合の補正(ケース1)
                        #       i
                        #    +------+   +-----+
                        # +-+
                        continue

                    if span["span"][1] < span_list[i]["span"][1]: # and span_list[i]["span"][0] < span["span"][1] 
                        # 挿入したspanと現在処理中のspan要素のstart位置との重なりがある場合の補正(ケース3)
                        #       i
                        #    +------+   +-----+
                        #  +---+
                        L = list(out[-1]["span"])
                        L[0] = span["span"][1]
                        out[-1]["span"] = tuple(L)
                        continue

                    if span_list[i]["span"][0] < span["span"][1]: #and span_list[i]["span"][1] <= span["span"][1]
                        # 挿入したspanが現在処理中のspan要素を包含する場合の補正(挿入したspanを削除、ケース4)
                        #      i
                        #    +------+   +-----+
                        #  +---------+
                        out.pop() # 最後にappendしたspan_list[i]を削除
                        
                        if i == len(span_list)-1:
                            continue # 最後のfor反復の為、何もせず抜ける(breakと等価)

                        # span_list[i+1](以降)の処理
                        for j in range(i+1, len(span_list)):
                            if span["span"][1] <= span_list[j]["span"][0]:
                                #                    j      j+1
                                #   +------+  ... +-----+ +-----+ ...
                                # +----------+
                                break # for-i 反復に戻る

                            if span["span"][1] < span_list[j]["span"][1]: # and span_list[j]["span"][0] < span["span"][1]
                                # 挿入したspanが1つ(以上)のspan要素を包含、その後のspanと重なりがある場合、ケース7)
                                #                    j      j+1
                                #   +------+  ... +-----+ +-----+ ...
                                # +------------------+
                                exc[j] = False # span_list[j]は処理不要とマークする
                                
                                # 新spanの追加
                                d = span_list[j].copy()
                                d["span"] = (span["span"][1], span_list[j]["span"][1])
                                out.append(d)
                                # for-j反復が続くのでbreakはしない
                            
                            else: # if span_list[j]["span"][1] <= span["span"][1]:
                                # 挿入したspanが1つ(以上)のspan要素を包含、その後のspanとの重なりはない場合、ケース8)
                                #                    j      j+1
                                #   +------+  ... +-----+ +-----+ ...
                                # +----------------------+
                                exc[j] = False
                                # for-j反復が続くのでbreakはしない

        if ins == False:
            out.append(span) 
            #                last 
            #   +------+   +-----+
            #                      +--+ (for反復後)
            # 挿入するspanが既存の最終要素のレンジと重ならない(ケース9))      
            if span_list[-1]["span"][1] <= span["span"][0]:
                pass
            else:
                #                last 
                #   +------+   +-----+
                #                +--+ (for反復後)
                #
                # または
                #                last  
                #   +------+   +-----+
                #              +-------+
                #
                # または
                #                last  
                #   +------+   +-----+
                #                   +---+
                # 挿入するspanが既存の最終要素のレンジと重なる・あるいは含まれる場合・・既存要素を削除しspan追加(ケース6))            
                out.pop(-2) # 最後から2つ目の要素(span_list[-1]の複写)を削除

                if span_list[-1]["span"][0] == span["span"][0]:
                    pass
                
                elif span_list[-1]["span"][0] < span["span"][0]:
                    d = span_list[-1].copy()
                    d["span"] = (span_list[-1]["span"][0], span["span"][0]) # タプル
                    out.insert(-1, d) # 最後(-1)の要素の前に挿入

                if span["span"][1] < span_list[-1]["span"][1]:
                    d = span_list[-1].copy()
                    d["span"] = (span["span"][1], span_list[-1]["span"][1])
                    out.insert(len(out), d) # 最後の要素に追加(out.append(d)と等価)

        return out


    @staticmethod
    def renew_span_range(span_list:list, length:int, s:int = 0)-> list:
        '''
        span_list内spanレンジ範囲(start/stop番号)の更新を行う
        入力
        span_list : "span"情報を要素に持つ辞書のリスト
        len       : start/stop番号の更新数
        s         : 更新を開始するspan番号(0,1,2...)

        本メソッドの目的と用途
        正規表現によるキャプチャデータ取得が実行された後に元コマンド内容に対し文字挿入する場合、
        既に取得済みのspan(start, stop)情報を更新する(挿入された文字数を加算する)必要があり、その操作を本メソッドで実行する
        (元情報で取得したspan情報のままターミナル出力に使用してしまった場合、挿入された文字数分のハイライト表示がずれてしまう)

        実現例を以下に示す(len=3/s=0、すなわち最初のspan情報のstart/stopから後のspan全てを3だけ更新する場合)
            入力   :[{..., "span":(17,19),...}, {..., "span":(20,23),...},]
            出力   :[{..., "span":(20,22),...}, {..., "span":(23,26),...},]
        '''

        # span_listチェック
        if CommandLevelList.check_span_list(span_list) == None: pass

        out = []
        for i in range(s, len(span_list)):
            d_new = span_list[i].copy()            
            if "span" in span_list[i]:
                d_new["span"] = (span_list[i]["span"][0] + length, span_list[i]["span"][1] + length)
            out.append(d_new)
        return out


class Base(CommandLevelList):
    '''
    比較・算術計算メソッド定義用ベースクラス
    各メソッドで使用するpattern, ptnについてはBaseを継承する各クラスで固有の値を設定する
    '''
    def __init__(self, cll: "CommandLevelList"):
        super().__init__(cll.data, cll.levels)

        
    def __eq__(self, cll2)-> bool:
        ''' 比較ベースメソッド(eq)
        自インスタンスおよび引数で指定されたインスタンス変数の各リスト要素に対し、
        指定された正規表現パターンの内容でマッチを取った結果が集合として一致した場合にTrueを返す
        
        注意事項
        matches_to_patternが返すリストはNoneを含むため、Noneの有無も差分となる
        '''
        if self.ptn != 3:
            return set(self.matches_to_pattern(self.ptn)[0]) == \
                   set(cll2.matches_to_pattern(self.ptn)[0])
        else:
            return set(self.matches_to_pattern(self.ptn, pattern = self.pattern)[0]) == \
                   set(cll2.matches_to_pattern(self.ptn, pattern = self.pattern)[0])
    

    def __le__(self, cll2)-> bool:
        ''' 比較メースメソッド(le)
        自インスタンスおよび引数で指定されたインスタンス変数の各リスト要素に対し、
        指定された正規表現パターンの内容でマッチを取り、前者が後者の部分集合を成す場合にTrueを返す 
        '''
        if self.ptn != 3:
            return set(self.matches_to_pattern(self.ptn)[0]) <= \
                   set(cll2.matches_to_pattern(self.ptn)[0])
        else:
            return set(self.matches_to_pattern(self.ptn, pattern = self.pattern)[0]) <= \
                   set(cll2.matches_to_pattern(self.ptn, pattern = self.pattern)[0])

    

    def __sub__(self, cll2)-> 'CommandLevelList':
        ''' 算術計算ベースメソッド(sub)
        自インスタンスおよび引数で指定されたインスタンス変数の各リスト要素に対し、
        指定された正規表現パターンの内容でマッチを取った結果の差集合を返す
        '''
        if self.ptn != 3:
            m1 = self.matches_to_pattern(self.ptn)[0]  
            diff = set(self.matches_to_pattern(self.ptn)[0]) - \
                   set(cll2.matches_to_pattern(self.ptn)[0])
        else:
            m1 = self.matches_to_pattern(self.ptn, pattern = self.pattern)[0]
            diff = set(self.matches_to_pattern(self.ptn, pattern = self.pattern)[0]) - \
                   set(cll2.matches_to_pattern(self.ptn, pattern = self.pattern)[0])
    
        out = []; out_level = []
        for x, y, lv in zip(m1, self.data, self.levels):
            for s in diff:
                if s == x:
                    out.append(y)
                    out_level.append(lv)
        # 現在のインスタンスが属するクラスのインスタンス
        return self.__class__(CommandLevelList(out, out_level))

    
    def to_cll(self)-> 'CommandLevelList':        
        ''' CommandLevelListへの型変換メソッド '''
        # levelsのすべての辞書内"level"要素、および処理対象レベルを"1"に更新し返す
        cll = self.renew_level(lv = "1")
        return CommandLevelList(cll.data, cll.levels, lv = "1")

    
class CommandListNetwork(Base):
    ''' 比較・算術計算メソッド定義用クラス(ipv4_network) '''
    def __init__(self, cll: 'CommandLevelList') -> None:
        super().__init__(cll)
        self.levels = cll.levels
        self.ptn = 2


class CommandListAddress(Base):
    ''' 比較・算術計算メソッド定義用クラス(ipv4_address) '''
    def __init__(self, cll: 'CommandLevelList') -> None:
        super().__init__(cll)
        self.levels = cll.levels
        self.ptn = 1
    
    
class CommandListString(Base):
    ''' 比較・算術計算メソッド定義用クラス(str) '''
    def __init__(self, cll: 'CommandLevelList', pattern: str) -> None:
        super().__init__(cll)
        self.levels = cll.levels
        self.pattern = pattern
        self.ptn = 3
    

    def __sub__(self, cll: 'CommandLevelList'):
        ''' 算術計算ベースメソッド(sub) '''

        if self.ptn != 3: # 3のはずなので冗長処理
            m1 = self.matches_to_pattern(self.ptn)[0]
            diff = set(self.matches_to_pattern(self.ptn)[0]) - \
                   set(cll.matches_to_pattern(self.ptn)[0])
        else:
            m1 = self.matches_to_pattern(self.ptn, pattern = self.pattern)[0] 
            diff = set(self.matches_to_pattern(self.ptn, pattern = self.pattern)[0]) - \
                   set(cll.matches_to_pattern(self.ptn, pattern = self.pattern)[0])

        out = []; out_level = []
        for x, y, lv in zip(m1, self.data, self.levels):
            for s in diff:
                if s == x:
                    out.append(y)
                    out_level.append(lv)
                    
        return CommandListString(CommandLevelList(out, out_level), self.pattern)  



# データ定義

default_route = ["0.0.0.0/0",
                 "0.0.0.0 0.0.0.0",
                ]

SPACE                                 = chr(0x0020) # " "(空白,ASCII)
IDEOGRAPHIC_SPACE                     = chr(0x3000) # "　"(和字間隔(CJKV,全角スペース)

WHITE_CIRCLE                          = chr(0x25CB) # "○"
LARGE_CIRCLE                          = chr(0x25EF) # "◯"
MEDIUM_WHITE_CIRCLE                   = chr(0x26AA) # "⚪"

# 罫線素片
BOX_DRAWINGS_LIGHT_VERTICAL_AND_RIGHT = chr(0x251c) # "├"(細線素片左)
BOX_DRAWINGS_LIGHT_UP_AND_RIGHT       = chr(0x2514) # "└"(細線素片左下)
BOX_DRAWINGS_LIGHT_VERTICAL           = chr(0x2502) # "│"(縦細線素片)
BOX_DRAWINGS_HEAVY_VERTICAL_AND_RIGHT = chr(0x2523) # "┣"(太線素片左)
BOX_DRAWINGS_HEAVY_UP_AND_RIGHT       = chr(0x2517) # "┗"(太線素片左下)
BOX_DRAWINGS_HEAVY_VERTICAL           = chr(0x2503) # "┃"(縦太線素片)


# 出力タイトル定義
# 形式
# "kind"  : s/n-標準版出力/preview版出力
# "print" : p/n-標準出力(コンソール)への出力をする/しない
# "title" : 出力タイトル文字列
# {
#   "1" : ({"kind" : 's', "print" : 'p', "title" : [表示タイトル-1.1, 表示タイトル-1.2]},
#        {"kind" : 's', "print" : 'p', "title" : [表示タイトル-2.1, 表示タイトル-2.2]},..
#        
#        {"kind" : 'n', "print" : 'p', "title" : [備考タイトル-1]},..
#        {"kind" : 'n', "print" : 'n', "title" : [備考タイトル-2]},
#       ),
#   "2" : ({"kind" : 's', "print" : 'p', "title" : [表示タイトル-1]},
#        {"kind" : 's', "print" : 'p', "title" : [表示タイトル-2]},..
#        
#        {"kind" : 'n', "print" : 'n', "title" : [備考タイトル-1]},
#        {"kind" : 'n', "print" : 'n', "title" : [備考タイトル-2]},..
#       ),
# }
title_dict_for_each_reqno = \
{'1': [{'kind': 's', 'print' : 'p', 'title': ['(1)ACLと受信用経路フィルタ突合', '●ACL']},
  {'kind': 's', 'print' : 'p', 'title': ['●受信経路フィルタ']},
  {'kind': 'n', 'print' : 'p', 'title': ['●エラーコマンドの表示']},
  {'kind': 'n', 'print' : 'p', 'title': ['●受信経路フィルタで許可されている対向側アドレスがACLに含まれているか', 'ACLに含まれていない受信経路コマンド']}],
 '2': [{'kind': 's', 'print' : 'p', 
   'title': ['(2)Staticルートと「StaticルートをBGPに再配送するための経路フィルタ」突合', '●Staticルート']},
  {'kind': 's', 'print' : 'p', 'title': ['●StaticルートをBGPに再配送するための経路フィルタ']},
  {'kind': 'n', 'print' : 'p', 'title': ['●a)Staticルート:#2-1で取得', '  b)WAN向けStaticルート：#7-1で取得', '  c)デフォルトルート：0.0.0.0/0', '  d)ダミースタティックルート：#6-1で取得', ' →a) - b) -c) -d)を表示']},
  {'kind': 'n', 'print' : 'p', 'title': ['●突合差分']}],
 '3': [{'kind': 's', 'print' : 'p', 
   'title': ['(3)「StaticルートをBGPに再配送するための経路フィルタ」と「StaticルートをBGPに再配送するためのルートマップ」突合', '●StaticルートをBGPに再配送するための経路フィルタ']},
  {'kind': 's', 'print' : 'p', 'title': ['●StaticルートをBGPに再配送するためのルートマップ']}],
 '4': [{'kind': 's', 'print' : 'p', 
   'title': ['(4)Directルート(LAN-IF設定)と「DirectルートをBGPに再配送するための経路フィルタ」突合', '●Directルート(LAN-IF設定)']},
  {'kind': 's', 'print' : 'p', 'title': ['●DirectルートをBGPに再配送するための経路フィルタ']},
  {'kind': 'n', 'print' : 'p', 'title': ['●Directルート(LAN-IF設定)のアドレス情報よりネットワークアドレスを特定し先頭に付加']},
  {'kind': 'n', 'print' : 'p', 'title': ['●突合差分']}],
 '5': [{'kind': 's', 'print' : 'p', 
   'title': ['(5)「StaticルートをBGPに再配送するための経路フィルタ」「DirectルートをBGPに再配送するための経路フィルタ」と経路広告用フィルタ突合', '●StaticルートをBGPに再配送するための経路フィルタ']},
  {'kind': 's', 'print' : 'p', 'title': ['●DirectルートをBGPに再配送するための経路フィルタ']},
  {'kind': 's', 'print' : 'p', 'title': ['●経路広告用フィルタ']}],
 '6': [{'kind': 's', 'print' : 'p', 
   'title': ['(6)ダミーSaticルートと、ダミーStaticルートに適用するBFD設定と、ダミーStaticルートを条件とするTrack設定突合', '●ダミーStaticルート(宛先が/32でかつ出力IFが「EthernetX/X.XXX」のもの)']},
  {'kind': 's', 'print' : 'p', 'title': ['●ダミーStaticルートに適用するBFD設定の候補']},
  {'kind': 's', 'print' : 'p', 'title': ['●ダミーStaticルートを条件とするTrack設定の候補']},
  {'kind': 's', 'print' : 'p', 
   'title': ['●ダミーStaticルートに適用するBFD設定でGWアドレスがダミーStaticルートと同一のもの']},
  {'kind': 's', 'print' : 'p', 'title': ['●ダミーStaticルートを条件とするTrack設定']}],
 '7': [{'kind': 's', 'print' : 'p', 'title': ['(7)WAN-IFアドレスと、BGPネイバー設定の突合', '●WAN-IF']},
  {'kind': 's', 'print' : 'p', 'title': ['●BGPネイバー設定']}],
 '8': [{'kind': 's', 'print' : 'p', 'title': ['(8)LoopbackIFと、BGPルータIDの突合', '●LoopbackIF']},
  {'kind': 's', 'print' : 'p', 'title': ['●BGPルータID']}],
 '9': [{'kind': 's', 'print' : 'p', 'title': ['(9)WAN-IF設定「interface EthernetXX.<Sub-IF番号>」と、WAN-IFで指定する「encapsulation dot1q <VLAN番号>」の突合']}],
 '10': [{'kind': 's', 'print' : 'p', 'title': ['(10)LAN-IF(Port-Channel IF)の「interface port-channelXX.<Sub-IF番号>」と、LAN-IFで指定する「encapsulation dot1q <VLAN番号>」の突合']}],
 '11': [{'kind': 's', 'print' : 'p', 'title': ['(11)「DirectルートをBGPに再配送するための経路フィルタ」と、「DirectルートをBGPに再配送するためのルートマップ」の突合', '●DirectルートをBGPに再配送するための経路フィルタ']},
  {'kind': 's', 'print' : 'p', 'title': ['●DirectルートをBGPに再配送するためのルートマップ']},
  {'kind': 'n', 'print' : 'p', 'title': ['●突合差分']}],
 '14': [{'kind': 's', 'print' : 'p', 
   'title': ['(14)BGP設定、Static/DirectルートをBGPに再配送するためのルートマップ、経路フィルタの突合', '●BGP設定(Static)']},
  {'kind': 's', 'print' : 'p', 'title': ['●StaticルートをBGPに再配送するためのルートマップ']},
  {'kind': 's', 'print' : 'p', 'title': ['●StaticルートをBGPに再配送するための経路フィルタ']},
  {'kind': 's', 'print' : 'p', 'title': ['●BGP設定(Direct)']},
  {'kind': 's', 'print' : 'p', 'title': ['●DirectルートをBGPに再配送するためのルートマップ']},
  {'kind': 's', 'print' : 'p', 'title': ['●DirectルートをBGPに再配送するための経路フィルタ']},
  {'kind': 'n', 'print' : 'p', 'title': ['●階層構造の表示(Static)']},
  {'kind': 'n', 'print' : 'p', 'title': ['●階層構造の表示(Direct)']}],
 '15': [{'kind': 's', 'print' : 'p', 
   'title': ['(15)ACL設定と、それに紐付くリストとの突合', '●ip access-group設定']},
  {'kind': 's', 'print' : 'p', 'title': ['●ACL設定']},
  {'kind': 'n', 'print' : 'p', 'title': ['●階層構造の表示']}],
}



class RetryError(Exception):
    ''' リトライオーバ例外定義 '''
    pass


def get_yes_or_no(prompt: str, retries: int = 4, reminder: str = '入力してください') -> bool:
    '''入力プロンプト確認
    画面に文字表示を行い、確認の為の入力を要求しYesまたはNoを入力させ、その結果を返す。
    '''
    while True:
        ok = input(prompt)
        if ok in ('Y', 'y', 'YES', 'yes'):
            return True
        if ok in ('N', 'n', 'NO', 'No', 'no'):
            return False
        retries = retries - 1
        if retries < 0:
            raise RetryError
        print(reminder)



# コマンドプロンプトからの起動用
if __name__ == '__main__':

    # Python版数確認
    major = sys.version_info.major; minor = sys.version_info.minor
    if major != 3 or minor <= 3:  # Python 3.4以降を想定（Python 4がないこと前提）
        raise RuntimeError('Python version does not meet to run this program.')

    parser = argparse.ArgumentParser(
                         prog='python getconfigsummary.py',
                         formatter_class=CustomHelpFormatter,
                         usage='%(prog)s [option]... --f [file]',
                         description='''入力されたコンフィグファイルに関するサマリ生成を実行し結果を出力する''',
                         add_help=True, 
                        )

    parser.add_argument('arg1', nargs= '?', default=None, help="arg1(オプション) - p/s: preview/system指定、又は入力ファイル格納ディレクトリ") 
    parser.add_argument('arg2', nargs= '?', default=None, help="arg2(オプション) - 入出力ファイル格納ディレクトリ")
    parser.add_argument('arg3', nargs= '?', default=None, help="arg3(オプション) - 出力ファイル格納ディレクトリ")

    parser.add_argument('--f',  nargs='?', const='stdin', help="コマンドラインからの入力ファイル名指定ならびに標準コンソールへの出力実行")
    parser.add_argument('-j', '--json', action='store_true', default=False, help="levelsのjson形式dump")
    parser.add_argument('-n', '--line_number', action='store_true', default=False, help="行番号付加(開始番号=1)")
    parser.add_argument('-p', '--preview_mode', action='store_true', default=False, help="previewモード指定")
    parser.add_argument('-r', '--reqno', nargs= '*', type=int, help="要望番号指定")
    parser.add_argument('-s', '--system_mode', action='store_true', default=False, help="systemモード指定")
    parser.add_argument('-t', '--benchmarktest', action='store_true', default=False, help=argparse.SUPPRESS)
    parser.add_argument('-z', '--colorless', action='store_false', default=True, help="着色なし(colorless)")

    args = parser.parse_args()


    # コマンドラインから入力された引数の中に位置引数(positional argument)が存在するかどうかを判定
    # 存在すれば同一の意味を持つオプション引数に置き換え(argparse.Namespaceのオブジェクト属性書き換え)
    # 入力された他のオプション引数(置き換えられたオプション引数以外)は、そのまま後続の処理へ渡す

    argvs = [] # positional argument格納用リスト
    for elem in exclude_element([args.arg1, args.arg2, args.arg3], None):
        argvs.append(elem)

    arg_count = len(argvs)

    p  = r'p\b|preview\b'
    s  = r's\b|system\b'
    ps = r'sp\b|ps\b|systempreview\b|previewsystem\b'

    if arg_count == 0: 
        if platform.system() == 'Windows': # 'Windows'または'Linux'を前提 
            getconfigsummary(args)
        elif platform.system() == 'Linux':
            getconfigsummary(args, in_folder=os.path.join('/home/', uid), out_folder=os.path.join('/home/', uid))
    else: # 0以外
        mp = re.match(p, argvs[0]); ms = re.match(s, argvs[0]); mps = re.match(ps, argvs[0])

        if mp    : args.preview_mode = True
        elif ms  : args.system_mode  = True
        elif mps : args.preview_mode = True; args.system_mode  = True

        if arg_count == 1:
            if platform.system() == 'Windows':       
                if mp != None or ms != None or mps != None:
                    getconfigsummary(args)
                else:         # 例 : python getconfigsummary.py C:\Users     
                    getconfigsummary(args, in_folder=argvs[0], out_folder=argvs[0])
            elif platform.system() == 'Linux':
                if mp != None or ms != None or mps != None:
                    getconfigsummary(args, in_folder=os.path.join('/home/', uid), out_folder=os.path.join('/home/', uid))
                else:         # 例 : python getconfigsummary.py /home/user
                    getconfigsummary(args, in_folder=argvs[0], out_folder=argvs[0])
    
        elif arg_count == 2:
                if mp != None or ms != None or mps != None:
                              # 例 : python getconfigsummary.py p C:\Users
                    getconfigsummary(args, in_folder=argvs[1], out_folder=argvs[1])
                else:         # 例 : python getconfigsummary.py C:\Users C:\Data
                    getconfigsummary(args, in_folder=argvs[0], out_folder=argvs[1])
        elif arg_count >= 3:
                if mp != None or ms != None or mps != None:
                              # 例 : python getconfigsummary.py p C:\Users C:\Data
                    getconfigsummary(args, in_folder=argvs[1], out_folder=argvs[2])
                else:         # 例 : python getconfigsummary.py C:\Users C:\Data D:\Data (最後は無視)
                    getconfigsummary(args, in_folder=argvs[0], out_folder=argvs[1])