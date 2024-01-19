# -*- coding: utf-8 -*-

'''ip address処理用スクリプトファイル

Copyright (c) 2023-2024 Fujitsu Limited.  All rights reserved.

'''

__version__ = '1.01'

import sys
import re
from ipaddress import ip_address, IPv4Address, IPv4Network, \
                      IPv6Address, IPv6Network, NetmaskValueError 

major = sys.version_info.major; minor = sys.version_info.minor


# 正規表現用パーツ群
# 簡略版ipv4形式 A.B.C.Dであり各オクテットが0,00,000～999であるもの(0～255に限定しない)
ipv4_address_simple = r'''
    \b         # 単語の先頭の\bを追加("0100.100.0.0"のようなケースを許容しない)
    (?:[0-9]{1,3}\.){3}[0-9]{1,3}
    \b
    '''

# 詳細版ipv4形式 A.B.C.Dであり各オクテットが0～255に限定されるもの
ipv4_address = r'''
    \b         # \bは":"(コロン)と\wの間にもなりうるので、ipv6の最終32bit分定義(pattern_ipv6)にも使用可能
    (?:        # 非キャプチャ対象:A.B.C.(範囲0～255)の開始
     (?:       # 非キャプチャ対象:"|"(または)のグループ化
       [1-9]?[0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]   
     )
     \.        # "."
    ){3}       # 3回繰り返し 
    (?:[1-9]?[0-9]|1[0-9]{2}|2[0-4][0-9]|25[0-5]) # 最終オクテットD(範囲0～255)
    \b         # \b(単語の末尾)
               # これがないと、D部分が部分的にしかマッチしない事象(例として255にマッチさせたいが、
               # '|'で定義された最初の選択肢 [1-9]?[0-9]のパターンに成功し25にマッチ)が発生する
    '''

# ipv4形式 例として0.0.0.255表現のネットマスク用部品
ipv4_netmask1 = r'''
     \b         #
     (?:        # 各オクテットの使用値
                #>>> for i in range(0, 9):
                #...     print(2**i - 1, end='|')
                #...
                # 0|1|3|7|15|31|63|127|255|
               (?:0|1|3|7|15|31|63|127|255)(?:\.255){3}|
        0\.    (?:0|1|3|7|15|31|63|127|255)(?:\.255){2}|
     (?:0\.){2}(?:0|1|3|7|15|31|63|127|255)\.255|
     (?:0\.){3}(?:0|1|3|7|15|31|63|127|255)
     )
     \b
     '''

# ipv4形式 例として255.255.255.0表現のネットマスク用部品
ipv4_netmask2 = r'''
     \b         #
     (?:        # 各オクテットの使用値
                #>>> w = 0
                #>>> for i in range(7, 0, -1):
                #...     w += 2**i
                #...     print(w, end='|')
                #...
                #     128|192|224|240|248|252|254|
                 (?:0|128|192|224|240|248|252|254)\.0\.0\.0|
        255\.    (?:0|128|192|224|240|248|252|254)\.0\.0|
     (?:255\.){2}(?:0|128|192|224|240|248|252|254)\.0|
     (?:255\.){3}(?:0|128|192|224|240|248|252|254)
     )1961850531888    \b
     '''




# IPv4形式表現へのマッチを試み、成功した場合結果をキャプチャする際に使用するパターン定義
#
#   テキスト    →  groupが返すタプル
# 192.168.0.0  → ('192.168.0.0', )
#
# 備考：ipv4アドレス形式が2回以上現れた場合-例:192.168.0.10 255.255.255.0-は、
# 1つ目のアドレス(ここでは192.168.0.10)にのみマッチする
pattern_ipv4_address = r'''
    (?:\s{1}|^)        # 空白一文字または行頭
    (?P<ipv4_address>  # キャプチャ対象開始(名前付き)
    '''                                         + \
    ipv4_address                                + \
    r''')       # キャプチャ対象終了
    (?:         # 空白1文字または文末
        \s{1}   
        |
        $
                # 192.168.0.10/30の様にサブネットマスクが続くパターンを除外するため
                # 「空白1文字または$」のパターンを置く
                # "/"が存在するとその直前が単語の末尾になる("/"は\w(=[a-zA-Z0-9_])に含まれない)ため
                # 元々単語の末尾を示す\bは代用できない(\bを置いても"/"の直前までマッチする)
    )
    '''

# 以下3通りのipv4ネットワーク表現にマッチを試み、成功した場合結果をキャプチャする際に使用するパターン定義
# 例:           テキスト            →　　　   groupが返すタプル
# 1. 192.168.0.0 0.0.0.255      → ('192.168.0.0', '0.0.0.255')
# 2. 192.168.0.0 255.255.255.0  → ('192.168.0.0', '255.255.255.0')
# 3. 192.168.0.0/24             → ('192.168.0.0', '24')
# 上記1.および2.の表現にてipv4アドレス間の"/"は許容しない("/"の次には0～32の数字を期待=>別パターンで取得)

pattern_ipv4_network = r'''
    (?:\s{1}|^)        # 空白一文字または行頭
    (?P<ipv4_address>  # キャプチャ対象開始(名前付き)
    '''                                         + \
    ipv4_address                                + \
    r''')   # キャプチャ対象終了
    '''                                         + \
    r'''
    (?: # 2つの先読みアサーション「(?=...」の"|"(または・選択)による結合
        # いずれかにマッチした場合に直前までの(今回だと\s{1}または"/"の)マッチ成功とする         
        # 1つ目 - 空白文字s{1}の後にipv4アドレス形式文字列(+行末または空白1文字)が続く場合
          \s{1}(?= '''                          + \
          ipv4_address_simple + r'''(?:$|\s{1}))'''  + \
          r''' |       # または         
        # 2つ目 - "/"の後に数字1-2桁(ネットマスク)(+行末または空白1文字)が続く場合
         (?P<slash>/)    
         (?=[0-9]{1,2}(?:$|\s{1}))
    )   # 先読みアサーションの結合の閉じカッコ
    (?P<netmask>  # キャプチャ対象開始(名前付き) A.B.C.Dの形式、又は0~32の整数のパターンのいずれか
    '''                                         + \
    ipv4_netmask1 + r'|' + ipv4_netmask2 + r'|' + \
    r'''
    (?:[1-2]?[0-9]|3[0-2])
    )   # 全体のキャプチャ対象終了
    (?:\s{1}|$)
    '''

# ipv4アドレス・ネットマスク・アドレスの表現にマッチを試み、成功した場合結果をキャプチャする際に使用するパターン定義
# 例:
# 1. 10.10.10.0 255.255.255.0 192.168.0.1    　→ ('10.10.10.0', '255.255.255.0', '192.168.0.1')
# 2. 10.10.10.0/24 ..(別の文字列).. 192.168.0.1 → ('10.10.10.0', '24', '192.168.0.1')
pattern_ipv4_network_address2 = r'''
    (?:\s{1}|^)        # 空白一文字または行頭
    (?P<ipv4_address1> # キャプチャ対象開始
    '''                                         + \
    ipv4_address                                + \
    r''')              # キャプチャ対象終了
    '''                                         + \
    r'''
    (?:          
     \s{1}(?= '''                               + \
     ipv4_address_simple + r'''(?:$|\s{1}))'''  + \
     r'''  |          
     /    (?=[0-9]{1,2}(?:$|\s{1}))
    )
    (?P<netmask>       # キャプチャ対象開始
    '''                                         + \
    ipv4_netmask1 + r'|' + ipv4_netmask2 + r'|' + \
    r'''
    (?:[1-2]?[0-9]|3[0-2])  # 0～9または10～29または30～32
    )                  # キャプチャ対象終了 -- ここまで前定義のpattern_ipv4_networkと同じ
    (?:
     \s{1}  # 空白1文字
     |
     \s{1}.+\s{1} # 空白1文字、1回以上の任意の文字、空白1文字
    )
    '''                                         + \
    r'''(?P<ipv4_address2> # キャプチャ対象開始
    '''                                         + \
    ipv4_address                                + \
    r'''
    )       # キャプチャ対象終了
    (?:\s{1}|$)
    '''



# ipv4定義によるマッチならびにキャプチャ用正規表現のための関数
# 引数としてv4adrptn(str)を取り、正規表現パターン(str)を返す
# 簡易定義(各オクテット0,00,000~999の範囲を許可) - 「ipv4_address_simple」を設定
# 正式表現(各オクテットが0~255に限定されるもの)   - 「ipv4_address」を設定

# 1つ目と2つ目のアドレス間に空白1文字を挟んで隣接し、初めにrange指定があるもの(3つのipアドレスと見なす)
def f_pattern_3ipv4addresses_with_range(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^) 
    \b(?:range)\b
    \s{1}       
    (?P<ipv4_address>'''                        + \
    v4adrptn                        + \
    r')\s{1}(?P<ipv4_address1>'                 + \
    v4adrptn                         + \
    r''')\s{1}             # 貪欲マッチ(この後のパターン定義(ipv4_address_simple)でマッチパターンが固定されるため、
    (?:.*)                 # 貪欲でも非貪欲(.*?)でも効果は同じ)
    (?P<ipv4_address2> '''                      + \
    v4adrptn                         + \
    r''')
    (?:\s{1}|$)
    '''

# 1つ目と2つ目のアドレスが空白1文字を挟んで隣接し(ipアドレスおよびnetmaskと見なす)、
# 加えて3つ目のアドレスが空白に加え何かしらの文字を挟んで存在するもの
# 例: ip route 0.0.0.0 0.0.0.0 10.10.10.129 
def f_pattern_ipv4netaddress_and_ipv4netmask_and_ipv4address(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^)                  
    (?P<ipv4_netaddress>'''                     + \
    v4adrptn                          + \
    r')\s{1}(?P<ipv4_netmask>'                  + \
    v4adrptn                          + \
    r''')\s{1}(?:.*)       # 貪欲マッチ
    (?P<ipv4_address> '''                       + \
    v4adrptn                          + \
    r''')
    (?:\s{1}|$)
    '''

# ipアドレス・ネットマスク(192.168.100.0/24等)およびアドレスが空白1文字+0個以上の文字を挟んで存在するもの
def f_pattern_ipv4network_and_ipv4address(v4adrptn :str)-> str:
    return r'''
    (?:\s{1}|^) 
    (?P<ipv4_network>'''                        + \
    v4adrptn                          + \
    r'''
     (?:/[1-2]?[0-9]|3[0-2]) 
    )\s{1}(?:.*)           # 貪欲マッチ
    (?P<ipv4_address>'''                        + \
    v4adrptn                          + \
    r''')
    (?:\s{1}|$)
    '''

# ipv4アドレスとネットマスク(あいだに空白1文字のみ存在するもの)
def f_pattern_ipv4netaddress_and_ipv4netmask(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^) 
    (?P<ipv4_netaddress>'''                     + \
    v4adrptn                         + \
    r''')\s{1}(?P<ipv4_netmask>'''              + \
    v4adrptn                         + \
    r''')
    (?:\s{1}|$)
    '''

# 2つのipv4アドレス(間に空白に加え何かの文字列が1つ以上存在)
def f_pattern_2ipv4addresses(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^)  
    (?P<ipv4_address>'''                        + \
    v4adrptn                          + \
    r''')\s{1}(?:.+)       # 貪欲マッチ
    (?P<ipv4_address1>'''                       + \
    v4adrptn                          + \
    r''')
    (?:\s{1}|$)
    '''

# 1つのipv4アドレス'192.168.0.0/24'の形式の為のパターン
def f_pattern_ipv4network(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^) 
    (?P<ipv4_network>'''                        + \
    v4adrptn                          + \
    r'''
     /(?:[1-2]?[0-9]|3[0-2]) 
    )
    (?:\s{1}|$)
    '''

# 1つのipv4アドレス用パターン
# 例として、'1100.100.8.4 0.0.0.3'のように前半('1100.100.8.4)が異常であっても、
# 後半の'0.0.0.3'部分をキャプチャ成功と扱ってしまうが、そのままとする
# (前の別パターン-pattern_std_ipv4netaddress_and_ipv4netmask-ではキャプチャ不成功となる)
def f_pattern_ipv4address(v4adrptn:str)-> str:
    return r'''
    (?:\s{1}|^) 
    (?P<ipv4_address> '''                       + \
    v4adrptn                         + \
    r''')
    (?:\s{1}|$)
    '''


# ipv6各オクテット部品
ipv6_two_octets = r'''
    [0-9a-f]{1,4}   # 0から9またはaからfから構成される1個から4個の文字列
    '''

# ipv6アドレス正規表現部品
# IPv4互換アドレス、IPv4射影アドレス(例 ::ffff:192.0.2.1)をサポート
# 2001:0db8:9abc::/48のようなサブネットマスク表記は別途(pattern_ipv6network)定義
pattern_ipv6 = r'''
    (?:
    \b      # 一つ前のカッコ「(?:」ではなく、この(最初が":"(colon)以外となる)場所で\bを置く
            # (空白と(colon)の間は単語の切れ目にならないので":"の前に\bを置くとマッチが失敗する)
            # >>> pattern = r'\b::/0'
            # >>> text    = '::/0'
            # >>> m = re.search(pattern, text)
            # >>> m == None
            # True         # (::/0"がキャプチャできない)
            #
     (?:    # "2001:db8:bd05:1d2:288a:1fc0:1:10ee"のように
            # 全16bitに実値が入るパターン
      (?:'''      + ipv6_two_octets + r':){7}(?:'   + \
                    ipv6_two_octets                 + \
       r'''\b # 単語の切れ目"\b"
            # または
        :)  # ":"のみ、すなわち"2001:db8:bd05:1d2:288a:1fc0:1::"のように
            # 最終16bitが'0'(省略)のパターン
     )|

     (?:    # "2001:db8:bd05:1d2:288a:1fc0::10ee"のパターン、すなわち
            # 第7フィールドが'0'(省略)、":"に続いて第8フィールドが来るパターン
              
        (?:'''    + ipv6_two_octets + r':){6}'      + \
        r'(?:'                                      + \
        r':'      + ipv6_two_octets                 + \
        r'''\b| 
            # "2001:db8:bd05:1d2:288a:1fc0:192.168.0.1"のように最終32bit分がipv4表現    
        r'''      + ipv4_address                    + \
        r'''\b|  
        :)  # ":"のみ、"2001:db8:bd05:1d2:288a:1fc0::"のように
            # 最終32bit分が'0'(省略)
     )|

     (?:    # "2001:db8:bd05:1d2:288a::1fc0:10ee"のパターン、または 
            # "2001:db8:bd05:1d2:288a::192.168.0.1"(最終32bit分がipv4表現)、または
            # "2001:db8:bd05:1d2:288a::"(最終48bit分が"0"(省略))
      
        (?:'''      + ipv6_two_octets + r':){5}(?:'   + \
        r'(?:(?::'  + ipv6_two_octets + r'){1,2})\b|:'  + \
                      ipv4_address                    + \
        r'''\b|:)
     )|

     (?:    # "2001:db8:bd05:1d2::1fc0:1:10ee"のパターン、または  
            # "2001:db8:bd05:1d2::1fc0:192.168.0.1"、または
            # "2001:db8:bd05:1d2::"(最終64bit分が"0")
      
        (?:'''      + ipv6_two_octets + r':){4}(?:'   + \
        r'(?:(?::'  + ipv6_two_octets + r'){1,3})\b|' + \
        r'(?:(?::'  + ipv6_two_octets + r')?:'        + \
                      ipv4_address                    + \
         r''')
        \b|:)
     )|

     (?:    # "2001:db8:bd05::1d2:1fc0:1:10ee"のパターン、または  
            # "2001:db8:bd05::1d2:1fc0:192.168.0.1"、または
            # "2001:db8:bd05::"(最終80bit分が"0")

        (?:'''      + ipv6_two_octets + r':){3}(?:'   + \
        r'(?:(?::'  + ipv6_two_octets + r'){1,4})\b|' + \
        r'(?:(?::'  + ipv6_two_octets + r'){0,2}:'    + \
                      ipv4_address                    + \
         r''')
        \b|:)
     )|

     (?:    # "2001:db8::bd05:1d2:1fc0:1:10ee"のパターン、または  
            # "2001:db8::bd05:1d2:1fc0:192.168.0.1"、または
            # "2001:db8::"(最終96bit分が"0")
        (?:'''      + ipv6_two_octets + r':){2}(?:'   + \
        r'(?:(?::'  + ipv6_two_octets + r'){1,5})\b|' + \
        r'(?:(?::'  + ipv6_two_octets + r'){0,3}:'    + \
                      ipv4_address                    + \
        r''')
        \b|:)
     )|

     (?:    # "2001::db8:bd05:1d2:1fc0:1:10ee"のパターン、または  
            # "2001::db8:bd05:1d2:1fc0:192.168.0.1"、または
            # "2001::"(最終112bit分が"0")
        (?:'''      + ipv6_two_octets + r':){1}(?:'   + \
        r'(?:(?::'  + ipv6_two_octets + r'){1,6})\b|' + \
        r'(?:(?::'  + ipv6_two_octets + r'){0,4}:'    + \
                      ipv4_address                    + \
        r''')
        \b|:)
     )|

     (?::   # 最初に":"(colon)
            # "::db8:bd05:1d2:288a:1fc0:1:10ee" または
            # "::db8:bd05:1d2:288a:1fc0:192.168.0.1"(最終32bit分がipv4表現)または
            # "::"(128bit分が"0")
        (?:
          (?:(?::''' + ipv6_two_octets + r'){1,7})\b|'  + \
        r'(?:(?::'   + ipv6_two_octets + r'){0,5}:'   + \
                       ipv4_address                   + \
        r''')
        \b|:)
     )
    #\b     # ここには単語の切れ目(/b)を置かない(":"で終了しないパターンの最後に置く)
            # ":"(colon)と"/"(slash)の間は単語の切れ目ではない為、network prefixが続くパターンでマッチ不成功になる事象の回避)
            # >>> pattern = r'::\b/0'
            # >>> text    = '::/0'
            # >>> m = re.search(pattern, text)
            # >>> m == None
            # True         
            #
    )
    (?:%.+)?  # ネットワークインタフェース(キャプチャには未対応)
    '''

# ipv6アドレス表現にマッチを試み、成功した場合に結果をキャプチャする際に使用するパターン定義
# 例:           
# 1. 2001:db8:bd05:1d2:288a:1fc0:1:10ee    → ('2001:db8:bd05:1d2:288a:1fc0:1:10ee',)
# 2. ::db8:bd05:1d2:288a:1fc0:192.168.0.1  → ('::db8:bd05:1d2:288a:1fc0:192.168.0.1',)
pattern_ipv6address = r'''
    (?:\s{1}|^)        # 空白一文字または行頭
    (?P<ipv6_address>  # キャプチャ開始 '''       + \
    pattern_ipv6                                 + \
    r''')   # キャプチャ終了       
    (?:\s{1}|$)
    '''

# ipv6ネットワーク表現にマッチを試み、成功した場合に結果をキャプチャする際に使用するパターン定義
# 例:           
# 1. 2001:db8:bd05:1d2:288a:1fc0:1:10ee/123 → ('2001:db8:bd05:1d2:288a:1fc0:1:10ee/123',)
# 2. ::/0                                   → ('::/0',)
pattern_ipv6network = r'''
    (?:\s{1}|^)              
    (?P<ipv6_network>  # キャプチャ開始'''        + \
    pattern_ipv6                                 + \
    r'''      
    /
    (?:
    [1-9]?[0-9]|1[0-1][0-9]|12[0-8]
    )\b
    )                  # キャプチャ終了
    (?:\s{1}|$)
    '''

# ipv6ネットワーク・アドレス表現にマッチを試み、成功した場合に結果をキャプチャする際に使用するパターン定義
# 例:           
# 1. ::/0 next-hop 2001:ce8:a0:6::1 → ('::/0' , '2001:ce8:a0:6::1',)
pattern_ipv6network_address = r'''
    (?:\s{1}|^)
    (?P<ipv6_network>  # キャプチャ開始 '''       + \
    pattern_ipv6                                 + \
    r'''      
    /
    (?:
    [1-9]?[0-9]|1[0-1][0-9]|12[0-8]
    )\b
    )                  # キャプチャ終了
    \s{1}(?:.*)\s{1}
    (?P<ipv6_address>  # キャプチャ開始 '''       + \
    pattern_ipv6                                 + \
    r''')              # キャプチャ終了
    (?:\s{1}|$)
    '''


def extract_addresses(command: str, strict: bool=False, simple:bool= False)-> tuple:
    ''' コマンド列に含まれるipv4/ipv6文字列を検索し情報を返す 
    引数: コマンド文字列(str)
          詳細モード(bool):strict
    戻り値: キャプチャ結果(tuple)
            マッチ要素あり:マッチ全体およびキャプチャ個数分の以下の辞書から成るタプル
            1個目:キャプチャ1個目(Match.group(1))
            2個目:キャプチャ1個目(Match.group(2))
            ・・・
            内容
            (..., {アドレス種別, エラー有無, (start位置, stop位置)}, ...)
            アドレス種別(str): "atype"
              "A6" : ipv6アドレス
              "A4" : ipv4アドレス
              "N6" : ipv6ネットワーク
              "N4" : ipv4ネットワーク
              "M6" : ipv6ネットマスク
              "M4" : ipv4ネットマスク
              "SL" : "/"(slash)
            エラー有無  : "error" = None/"(エラー種別)" エラーなし/エラー有り
            スパン : "span" - start位置, stop位置からなるタプル
            マッチ要素無し:空のタプル
    処理概要
    ・ステップ1
      下記条件1あるいは条件2を満たす場合、ipaddressクラス処理を起動し結果を返す(ステップ2以降は実施しない)
      条件1:名前付きキャプチャ'ipv4_netaddress'および'ipv4_netmask'が存在し、
         m.group(1) == m.group('ipv4_netaddress')かつm.group(2) == m.group('ipv4_netmask')を満たす(ステップ1-1)
      条件2:条件1を満足しそれに加えて、
         名前付きキャプチャ'ipv4_address'が存在し、m.group(3) == m.group('ipv4_address')を満たす(ステップ1-2)
      いずれも条件を満たさない場合はステップ2へ
    ・ステップ2
      'ipv4_netaddress'および'ipv4_netmask'「以外の」名前付きキャプチャの存在確認を実施する
    ・ステップ3
      ipaddressクラスの起動結果を編集し呼び元に返す
    ''' 

    s = ipv4_address_simple if simple == True else ipv4_address 

    p1 = re.compile(f_pattern_3ipv4addresses_with_range(s), re.VERBOSE)
    p2 = re.compile(f_pattern_ipv4netaddress_and_ipv4netmask_and_ipv4address(s), re.VERBOSE)
    p3 = re.compile(f_pattern_ipv4network_and_ipv4address(s), re.VERBOSE)
    p4 = re.compile(f_pattern_ipv4netaddress_and_ipv4netmask(s), re.VERBOSE)
    p5 = re.compile(f_pattern_2ipv4addresses(s), re.VERBOSE)
    p6 = re.compile(f_pattern_ipv4network(s), re.VERBOSE)
    p7 = re.compile(f_pattern_ipv4address(s), re.VERBOSE)
    
    p8 = re.compile(pattern_ipv6network_address, re.VERBOSE)
    p9 = re.compile(pattern_ipv6network, re.VERBOSE)
    p10 = re.compile(pattern_ipv6address, re.VERBOSE)

    # タプル要素の順番は本質的 - 多く取れる正規表現パターンを先に、少なく取る正規表現を後に配置する      
    p_tuple = (p1,p2,p3,p4,p5,p6,p7,p8,p9,p10)   
    
    result = [] # 呼び元に返す直前でリスト=>タプル変換
    atype, atype_1, atype_2, atype_3 = "", "", "", ""
    error, error_1, error_2, error_3 = None, None, None, None
    
    for i in range(len(p_tuple)):
        m = re.search(p_tuple[i], command)
        if m: break # 次のパターンへ
    
    if not m: return tuple(result) # マッチ要素なしのケース、空きタプルを返す
    else:
        if len(m.groups()) >= 2:
            while True:
                # ステップ1-1
                try:
                    _ = m.group('ipv4_netaddress'); _ = m.group('ipv4_netmask')
                except (IndexError): 
                    break # while文を抜けステップ2へ
                else: 
                    pass # 'ipv4_netaddress'および'ipv4_netmask'の名前付きキャプチャが存在、次のif文へ

                if m.group(1) != m.group('ipv4_netaddress') or m.group(2) != m.group('ipv4_netmask'):
                    raise # パターン定義とのアンマッチ、エラー扱い
                
                try:
                    _ = IPv4Address(m.group(1))
                except (NetmaskValueError, ValueError) as err:
                    atype_1 = "A4"; error_1 = err
                    try:
                        _ = IPv4Address(m.group(2))
                    except (NetmaskValueError, ValueError) as err:
                        atype_2 = "M4"; error_2 = err
                    else:
                        atype_2 = "M4"; error_2 = None
                    return tuple(
                                 ({"atype":atype_1, "error":error_1, "span":m.span(1)},
                                  {"atype":atype_2, "error":error_2, "span":m.span(2)},)
                                )                                  # "span":(m.start(1), m.end(1))等と等価               
                else:
                    try:
                        _ = IPv4Address(m.group(2))
                    except (NetmaskValueError, ValueError) as err:
                        atype_1 = "A4"; error_1 = None
                        atype_2 = "M4"; error_2 = err
                        return tuple(
                                     ({"atype":atype_1, "error":error_1, "span":m.span(1)},
                                      {"atype":atype_2, "error":error_2, "span":m.span(2)},)
                                    )
                    else:
                        # 'ipv4_netaddress'および'ipv4_netmask'の名前付きキャプチャ双方ともエラーなし、次のtry文へ
                        pass

                try:
                    _ = IPv4Network_override((m.group(1), m.group(2)), strict=strict)
                except (NetmaskValueError, ValueError) as err:
                    atype_1 = "A4"; error_1 = err
                    atype_2 = "M4"; error_2 = err 
                else:
                    atype_1 = "A4"; error_1 = None
                    atype_2 = "M4"; error_2 = None 

                if len(m.groups()) == 2:
                    return tuple(
                                 ({"atype":atype_1, "error":error_1, "span":m.span(1)},
                                  {"atype":atype_2, "error":error_2, "span":m.span(2)},)
                                ) 
                else:
                    pass # 3つ以上の要素が存在するのでステップ1-2へ
                                   
                # ステップ1-2 : m.group(3) == m.group('ipv4_address')を期待する処理
                try:
                    _ = m.group('ipv4_address')
                except (IndexError) as err:
                    raise # パターン定義とのアンマッチ(3つ目のキャプチャがipv4_addressではない)、エラー扱い
                else:
                    pass #'ipv4_address'の名前付きキャプチャがエラーなし、次のif文へ

                if m.group(3) != m.group('ipv4_address'):
                    raise # パターン定義とのアンマッチ、エラー扱い

                try:
                    _ = IPv4Address(m.group(3))
                except (NetmaskValueError, ValueError) as err:
                    atype_3 = "A4"; error_3 = err
                else:
                    atype_3 = "A4"; error_3 = None
                return tuple(
                             ({"atype":atype_1, "error":error_1, "span":m.span(1)},
                              {"atype":atype_2, "error":error_2, "span":m.span(2)}, 
                              {"atype":atype_3, "error":error_3, "span":m.span(3)},)
                            )  

        # ステップ2 : 最大3つまでの処理(i=0,1,2) 4つ目以降が存在した場合は当面無視
        for i in range(0, min(len(m.groups()), 3)): 
            while True:
                try:
                    if m.group(i+1) ==  m.group('ipv4_address') or \
                                        m.group('ipv4_address1') or \
                                        m.group('ipv4_address2'): 
                        atype = "A4"; break # while文を抜けステップ3へ
                except IndexError: pass     # 次のtry文へ

                try: 
                    if m.group(i+1) == m.group('ipv4_network'): atype = "N4"; break 
                except IndexError: pass

                try:
                    if m.group(i+1) == m.group('ipv6_address'): atype = "A6"; break 
                except IndexError: pass

                try:
                    if m.group(i+1) == m.group('ipv6_network'): atype = "N6"; break 
                except IndexError: pass

                try:
                    if m.group(i+1) == m.group('netmask'): atype = "M4"; error = None; break 
                except IndexError: pass

                try:
                    if m.group(i+1) == m.group('slash'): atype = "SL"; error = None; break 
                except IndexError:
                    # いずれの名前付きキャプチャグループにも属さないケース(パターン定義とのアンマッチ)
                    raise
            
            # ステップ3
            if atype == "A4":
                try:
                    _ = IPv4Address(m.group(i+1))
                except (NetmaskValueError, ValueError) as err: error = err
                else: error = None

            if atype == "N4":
                try:
                    _ = IPv4Network_override(m.group(i+1), strict=strict)
                except (NetmaskValueError, ValueError) as err: error = err
                else: error = None

            if atype == "A6":
                try:
                    _ = IPv6Address(m.group(i+1))
                except (NetmaskValueError, ValueError) as err: error = err
                else: error = None

            if atype == "N6":
                try:
                    _ = IPv6Network(m.group(i+1), strict=strict)
                except (NetmaskValueError, ValueError) as err: error = err
                else: error = None

            result.append({"atype":atype, "error":error, "span":m.span(i+1)}) 
        
        return tuple(result)


def extract_ipv4address(command: str)-> 'ip_address':
    ''' コマンド列からipv4文字列を正規表現でキャプチャし結果を返す 
    引数: コマンド文字列(str)
    戻り値:
    マッチ要素あり:マッチ全体およびキャプチャ分の以下の辞書から成るタプル
            0個目:マッチ全体     (Match.group(0))
            1個目:キャプチャ1個目(Match.group(1))
            内容
            (..., {アドレス種別, エラー有無, (start位置, stop位置)}, ...)
            アドレス種別(str): "atype"
              "A4" : ipv4アドレス
            エラー有無  : "error" = None/"(エラー種別)" エラーなし/エラー有り
            スパン : "span" - start位置, stop位置からなるタプル
            "ipaddr": ipaddress型インスタンスのstr型 
    マッチ要素無し:空タプル
    '''    

    pattern = re.compile(pattern_ipv4_address, re.VERBOSE)
    if len(re.findall(pattern, command)) >= 2: # ipv4文字列が2つ以上存在
        return None        
    m = re.search(pattern, command)
    if m:
        try:
            return ({"atype":"A4", "error":None, "span":m.span(1),   \
                                   "ipaddr": str(ip_address(m.group('ipv4_address'))),}, \
                   )
        except ValueError as err:
            return ({"atype":"A4", "error":"ValueError: {0}".format(err), "span":m.span(1), \
                                   "ipaddr": None,}, \
                   )

    else: # 正規表現による取得失敗
        return tuple()

def extract_ipv4network(command: str, strict: bool = False)-> 'ip_address':
    ''' コマンド列からipv4文字列を正規表現でキャプチャしipv4networks型オブジェクトとして返す 
    引数: コマンド文字列(str)
          strict: 厳密モード(True/False)
            ipv4アドレスとサブネットマスク情報取得に成功した場合、strict値の内容により以下動作を行う
            True - ネットワークのhost bit部分に0でない値がセットされている場合は例外をスロー
                   (例: ValueError: 192.168.0.1/24 has host bits set)
            False - ネットワークのhost bit部分に0マスクを施した値を返す
    戻り値:
    マッチ要素あり:マッチ全体およびキャプチャ分の以下の辞書から成るタプル
            0個目:マッチ全体     (Match.group(0))
            1個目:キャプチャ1個目(Match.group(1)) -- 名前キャプチャ'ipv4_address'
            2個目:キャプチャ2個目(Match.group(2)) -- 名前キャプチャ'slash'(存在しないときはMatch.group(2)=None)
            3個目:キャプチャ3個目(Match.group(3)) -- 名前キャプチャ'netmask'
            内容
            (..., {アドレス種別, エラー有無, (start位置, stop位置)}, ...)
            アドレス種別(str): "atype"
              "A4" : ipv4アドレス
              "M4" : ipv4ネットマスク(A.B.C.Dの形式、又は0~32の整数のパターンのいずれか)
            エラー有無  : "error" = None/"(エラー種別)" エラーなし/エラー有り
            スパン : "span" - start位置, stop位置からなるタプル
            "ipaddress": ipaddress型インスタンスのstr型
    マッチ要素無し:空タプル
    '''    
    
    pattern = re.compile(pattern_ipv4_network, re.VERBOSE)
    m = re.search(pattern, command)
    if m:
        if m.group(2) == None:
            try:
                return ({"atype":"A4", "error":None, "span":m.span(1),   \
                                   "ipaddr": str(IPv4Network_override((m.group('ipv4_address'), \
                                                                   m.group('netmask')),     \
                                                                   strict=strict)),},        \
                    {"atype":"M4", "error":None, "span":m.span(3), }, \
                   )

            except ValueError as err:
                return ({"atype":"A4", "error":"ValueError: {0}".format(err), "span":m.span(1), \
                                   "ipaddr": None,}, \
                    {"atype":"M4", "error":"ValueError: {0}".format(err), "span":m.span(3), \
                                   "ipaddr": None,}, \
                   )
            
        else: # 名前キャプチャ'slash'が存在       
            try:
                return ({"atype":"A4", "error":None, "span":m.span(1),   \
                                   "ipaddr": str(IPv4Network_override((m.group('ipv4_address'), \
                                                                   m.group('netmask')),     \
                                                                   strict=strict)),},        \
                    {"atype":"M4", "error":None, "span":m.span(2), }, \
                    {"atype":"M4", "error":None, "span":m.span(3), }, \
                   )

            except ValueError as err:
                return ({"atype":"A4", "error":"ValueError: {0}".format(err), "span":m.span(1), \
                                   "ipaddr": None,}, \
                    {"atype":"M4", "error":"ValueError: {0}".format(err), "span":m.span(2), \
                                   "ipaddr": None,}, \
                    {"atype":"M4", "error":"ValueError: {0}".format(err), "span":m.span(3), \
                                   "ipaddr": None,}, \
                   )

    else: # 正規表現による取得失敗-空のタプルを返す
        return tuple()


class IPv4Network_override(IPv4Network):
    '''Python標準ライブラリipaddressのIPv4Networkクラスを継承し、
    以下目的を達成するためオーバライドメソッドを定義する

    - netmask"0.0.0.0"の扱いを変更する
    
    概要
    IPv4Networkの初期設定メソッドへ渡す引数address, netmaskについて
    addressが"0.0.0.0"以外の場合に限り、netmask"0.0.0.0"を"255.255.255.255"に置き換える
    addressが"0.0.0.0"の場合("0.0.0.0 0.0.0.0")は、default routeとして扱うため従来のルートを通す
    
    備考
    背景にあるのは以下2つの要件
    1. 例: "10.10.10.10" "0.0.0.0"に対して32bit maskを施し"0.0.0.0/0" ネットワークのhost addressと見なす
       ("10.10.10.10" "255.0.0.0"の場合、24bit maskを施し"10.0.0.0/8"ネットワークのhost addressと
       見なすことの延長)
    2. 例: "192.168.255.255", "0.0.0.0"に対して0bit maskにより"192.168.255.255" "255.255.255.255")と
       同一視、すなわち単独アドレスから構成される0bit mask長のネットワークであると見なす
       ("192.168.255.255" "0.0.0.1"の場合、1bit maskにより"192.168.255.254/31"と同一視することの延長)
       
    これらは互いに相反する動作のため同時に実現することは不可で、標準ライブラリでは1.が優先実現されているが、
    今回、直近の課題として2.の実装が必要となるため、標準クラスの初期化メソッドをオーバライドすることで対応
    '''
    def __init__(self, address, strict=True) -> None:
        
        if address is not None:
            if isinstance(address, tuple) and len(address) == 2:
                addr, netmask = address
                if (netmask == "0.0.0.0") and (addr != "0.0.0.0"):
                    address = (addr, "255.255.255.255")
            else:
                pass
        
        if major == 3 and minor >= 5:  # Python 3.5以降はタプル渡しをサポート
            super().__init__(address, strict=strict)
        else:
            super().__init__(address[0] + '/' + address[1], strict=strict)