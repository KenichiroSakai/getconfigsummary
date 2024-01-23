# -*- coding: utf-8 -*-

'''共通ユーティリティクラスおよび関数を定義する

Copyright (c) 2023-2024 Fujitsu Limited.  All rights reserved.

'''

__version__ = '1.01'

import os, sys
import argparse
import re

class TerminalColor:
    """ ターミナル色変更用クラス """
    
    if sys.platform.lower().startswith("win"):

        # WindowsにおけるSetConsoleModeの有効化 
        import ctypes

        # 定数定義の詳細
        # https://docs.microsoft.com/en-us/windows/console/setconsolemode?redirectedfrom=MSDN
        ENABLE_PROCESSED_OUTPUT = 0x0001
        ENABLE_WRAP_AT_EOL_OUTPUT = 0x0002
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        MODE = ENABLE_PROCESSED_OUTPUT + ENABLE_WRAP_AT_EOL_OUTPUT + ENABLE_VIRTUAL_TERMINAL_PROCESSING
 
        kernel32 = ctypes.windll.kernel32    # windllのエクスポート
        handle = kernel32.GetStdHandle(-11)
        kernel32.SetConsoleMode(handle, MODE)


    # 文字色(ANSIカラー、前背景)の指定: ESC[nm 
    INFO_BLACK   = '\033[30m'
    INFO_RED     = '\033[31m'
    INFO_GREEN   = '\033[32m'
    INFO_YELLOW  = '\033[33m'
    INFO_BLUE    = '\033[34m'
    INFO_MAGENTA = '\033[35m'
    INFO_CYAN    = '\033[36m'
    INFO_WHITE   = '\033[37m'

    # 背景色(Background color)の指定 
    BC_BLACK     = '\033[40m'
    BC_RED       = '\033[41m'
    BC_AO        = '\033[42m'
    BC_YELLOW    = '\033[43m'
    BC_BLUE      = '\033[44m'
    BC_MAGENTA   = '\033[45m'
    BC_CYAN      = '\033[46m'
    BC_WHITE     = '\033[47m'

    WARN         = '\033[93m'
    ERR          = '\033[91m'
 
    # フォントスタイル
    MARKER       = '\033[7m'
    BOLD         = '\033[1m'
    UNDERLINE    = '\033[4m'
 
    # 末尾制御(属性を標準に戻す)
    _END         = '\033[0m'

    @classmethod
    def c_print(cls, text, styles=()):
        colored_text = ""
        for style in styles:
            colored_text += style
 
        colored_text += text
        colored_text += cls._END
        print(colored_text, end="") # 行最後以外の部分文字列に着色

    @classmethod
    def c_line_print(cls, text, styles=()):
        colored_text = ""
        for style in styles:
            colored_text += style
 
        colored_text += text
        colored_text += cls._END
        print(colored_text) # 行全体に着色

    @classmethod
    def print_ansi_color(cls, args: argparse.Namespace):
        ''' ANSIカラーの表示
        '8'     - 色(0-7, ANSIカラー)
        '256'   - 拡張用(0-255カラーパレット) 
        '256_b' - 拡張用(0-255カラーパレット,背景色)
        '''        
        if args.color == '8':
        #    for i in range(10):
            for i in range(13):
                for j in range(10):
                    v = i * 10 + j
                    print("\033[{}m{}\033[0m ".format(str(v), str(v).zfill(3)), end="")
                print("")

        if (args.color == '256') | (args.color == '256_b'): 
            for i in range(16):
                for j in range(16):
                    v = i * 16 + j
                    if args.color == '256':
                        print("\033[38;5;{}m{}\033[0m ".format(str(v), str(v).zfill(3)), end="") # 例 - \033[38;5;123m
                    else:
                        print("\033[48;5;{}m{}\033[0m ".format(str(v), str(v).zfill(3)), end="") # 例 - \033[48;5;123m
                print("")


def get_encode(filepath)-> str or None:
    ''' ファイルの文字コードを判定する 
    引数: ファイルパス(str)
    戻り値: ファイルの文字コード(str) or None(判定不能)
    説明:
    utf_16 ⇒ utf_8_sig ⇒ euc_jp ⇒ cp932の順にencodingを試し、最初に例外発生が無かったencodingを返す
    全てのencodingにおいて例外が発生した場合はNoneを返す(バイナリファイル等のケース)
    
    エンコーディング候補についての補足説明
    使用されるテキストファイルがMicrosoft Excelから書き出された場合を想定しcp932またはUTF-8に対応させる
    また、Linux上で動作させるケースを考慮しeuc_jpにも対応させる

    encoding試行順序についての補足説明
    入力ファイルに含まれる文字は(ASCIIおよび)通常の日本語の範囲に限定する
    cp932の1バイト符号化文字(JIS X 0201)の場合、0xA1-0xDF(半角カタカナ)
    cp932の2バイト符号化文字(JIS X 0208)の場合、第一バイトが0x81-0x9F, 0xE0-0xEF, 第二バイトが0x40-0x7E, 0x80-0xFC
    euc-jpの2バイト符号化文字の場合、第一,第二バイトが0xA1-0xFE(半角カタカナの場合は1バイト符号化、0xA1-0xDF)
    utf-8の3バイト符号化文字(日本語はここに含まれる)の場合、第一バイトが0b1110xxxx, 第二,第三バイトが0b10xxxxxx

    ⇒cp932のencodingを先に試すと、euc-jp/utf-8でエンコーディングした文字を別の文字に変換してしまう可能性がある
      (euc_jpの全角スペース(0xA1A1)をcp932でencodingすると半角句点2個になる、等)

    ASCII以外の文字の例として全角Space「　」、WHITE_CIRCLE 「○」に対するエンコーディング指定毎の動作差分

                                 全角Space                |               White Circle
    encoding| cp932(0x8140) |utf-8(U+3000)|euc_jp(0xA1A1) | cp932(0x819B)| utf-8(U+25CB)| euc_jp(0xA1FB)
    -------- --------------- ------------- ------------- -------------- -------------- -----------------
    cp932   |     OK        | 別文字に変換 | 別文字に変換   |     OK       |   Error      |    Error
    UTF-8   |    Error      |     OK      |     Error     |    Error     |     OK       |    Error
    euc_jp  |    Error      |    Error    |      OK       |    Error     |   Error      |     OK

    この例に示す通り、cp932で先にencodingを試すと全角Spaceがファイル内に存在する場合、
    意図と反して別の文字に変換(文字化け)しエラーとは出来ないため例外をraise出来ない    

    Shift-JISエンコーディング指定には、Shift-JISの拡張文字コードセットであるcp932を用いる
    UTF-8エンコーディング指定には、BOM(Byte Order Mark)の存在を考慮しutf_8_sigを用いる    
    '''

    encs = ('utf_16', 'utf_8_sig', 'euc_jp', 'cp932')
    r = None

    for enc in encs:
        with open(filepath, encoding=enc) as f:
            try:
                f = f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue
            else:
                r = enc
                break       
    return r



def rm_escseq(args: argparse.Namespace) -> None:
    ''' ANSIエスケープシーケンスを削除する
    '''

    # 20240104
    # raw 文字列記法の使用:Python 3.12にてSyntaxWarning: invalid escape sequence '\['となることの回避
    # ("re.compile()引数に対しraw文字列記法を適用)

    pattern = re.compile(r'''
        \x1b            # ESC(16進表記「\x1b」, 8進表記「\033」) 
        \[              # 
        ([0-9]{1,}      # 基本例 - ESC[xxm の場合のxx(例:31-red) 
         (
          (;[0-9]{1,})* # 拡張例 - ESC[38;5;xxxm の場合のxxx:拡張用カラーコード(0-255) 
         )?
        )?              # 0または1個, 数字無し - ESC[m (リセットコード)の場合は0個
        m               # m - SGR (Select Graphic Rendition)を表す
        ''', re.VERBOSE)

    try:
        if args.f == None: # コマンドラインからのファイル名指定
            print('ファイルの指定が必要です'); return
        
        in_path = os.path.join(os.getcwd(), args.f)
        if not os.path.exists(in_path):
            print('ファイル ' + args.f + ' が見つかりません'); return
            
        if args.encoding != False:
            with open(in_path, "r", encoding=args.encoding) as f: # コマンドラインからの指定値
                try:
                    text = f.read()
                except(UnicodeDecodeError, UnicodeError): 
                    raise
        else:
            enc = get_encode(in_path)
            if enc == None: 
                raise UnicodeError
            with open(in_path, "r", encoding=enc) as f:
                text = f.read()         
   
        m = re.subn(pattern, "", text) # タプル(new_string, number_of_subs_made)を返す
        print(m[0])
        
        if args.output_detail == True:
            print(str(m[1]) + "個の文字列を置換しました")

    except(KeyboardInterrupt):
        print('強制中断されました')
    except(UnicodeDecodeError, UnicodeError):
        print('文字コードを確認してください')
    except:
        raise
    


def standard_out(command, i, result, t_length:int =None, n:bool =False, z:bool = True)-> None:   
    '''標準出力を実行する
    入力: コマンド文字列(str)   : command
          コマンド行番号(int)   : i (-1: 区切り表示(---)等の単独出力)、0: 未使用、1~:コマンド)
          キャプチャ情報(list)  : result(辞書のリスト)
                                 例:
                                 [{"atype":"INFO", "error":None,        "span":(17,19)},
                                  {"atype":"A4", "error":"ValueError", "span":(20,23)},
                                  ...,],
          元テキスト行数(int)   : t_length(コマンド行番号の桁数を決定するのに使用)
          行番号出力指示(bool)  : n (True/False:出力する/しない)
          色付けの有無(bool)    : z (True/False:色付けする/しない)
    戻り値: 無し
    '''
    term_c = TerminalColor() # インスタンス化

    # ANSI基本色
#    style_boldred    = (term_c.BOLD, term_c.INFO_RED,)      # データ照合用ハイライト
#    style_boldyellow = (term_c.BOLD, term_c.INFO_YELLOW,)   # エラー表示用ハイライト
#    style_boldgreen  = (term_c.BOLD, term_c.INFO_GREEN,)    # 行番号
#    style_boldcyan   = (term_c.BOLD, term_c.INFO_CYAN,)     # 検索文字用ハイライト

    # ANSI拡張色
    # '\033[38;5;xxxm'のxxxには0-255のカラーコードを指定する(cd common; python util.py -c 256で表示可能)
    style_boldred_ext    = (term_c.BOLD, '\033[38;5;171m',) # データ照合用ハイライト
    style_boldyellow_ext = (term_c.BOLD, '\033[38;5;223m',) # エラー表示用ハイライト
    style_boldgreen_ext  = (term_c.BOLD, '\033[38;5;010m',) # 行番号
    style_boldcyan_ext   = (term_c.BOLD, '\033[38;5;014m',) # 検索文字用ハイライト

    style_boldred    = style_boldred_ext
    style_boldyellow = style_boldyellow_ext
    style_boldgreen  = style_boldgreen_ext
    style_boldcyan   = style_boldcyan_ext  

    if i == -1:
        if z == True:
            term_c.c_print(command, style_boldgreen); print("")
            return
        else:
            print(command)
            return 

    if n == True:
        col = ":" if result != () else "-"
        if z == True:
            if t_length != None:
                term_c.c_print(str(i).zfill(len(str(t_length))), style_boldgreen) # 元ファイル行数の桁数を出力(左ゼロ詰め)   
            else:
                term_c.c_print(str(i), style_boldgreen)
            term_c.c_print(col, style_boldgreen) 
            print("", end='')
        else: # colorless
            if t_length != None:            
                print(str(i).zfill(len(str(t_length))), col , sep="", end='')
            else:
                print(str(i), col , sep="", end='')


    if result == (): # キャプチャ要素無し
        print(command)            
        return

    # 先頭部分のキャプチャ非対象部分(先頭からキャプチャがあればここは""(空文字))
    print(command[0:result[0]["span"][0]], end='') 

    for j in range(len(result)):
        if z == True:
            if result[j]["atype"] == "INFO":
                style = style_boldcyan
            else:
                if result[j]["error"] == None:
                    style = style_boldred
                else:
                    style = style_boldyellow
            term_c.c_print(command[result[j]["span"][0]:result[j]["span"][1]], style)
        else:
            print(command[result[j]["span"][0]:result[j]["span"][1]], end='')
            
        if j+1 != len(result):
            print(command[result[j]["span"][1]:result[j+1]["span"][0]], end='')
        else:
            # >>> s = 'abcde'; len(s)
            # 5
            # >>> s[3:]   # スライスの最後まで(s[3:len(s)]と同義)
            # 'de'
            # >>> s[4:]
            # 'e'
            print(command[result[j]["span"][1]:], end='') # 最終spanのstopからコマンド列の最後の文字まで

    print("") 


def exclude_element(data, e):
    ''' data内の引数e以外の要素を逐次返すジェネレータ '''
    for x in data:
        if x != e: yield(x)



class Tuple_Iterator():
    ''' イテレータベースクラス 
    引数aと引数bそれぞれの同一インデックス値を持つ情報をタプルにして返す
    '''
    def __init__(self, a, b) -> None:
        self.a = a
        self.b = b
        self.index = 0
        
    def __iter__(self):
        return self
    
    def __next__(self):
        if self.index == len(self.a) or self.a == [] or self.b == []:
            raise StopIteration
        self.index = self.index + 1
        return self.a[self.index-1], self.b[self.index-1]


class CustomHelpFormatter(argparse.HelpFormatter):
    ''' HelpFormatterクラスを継承し、下記目的を実現するオーバライドメソッドを定義する
    - ヘルプ表示の改行位置調整
    - ヘルプ表示の英語表現の日本語化

    いずれもコマンドラインからの起動時におけるヘルプ表示の体裁を変更するのみであり、
    argparserのコマンドライン引数パラメータ解析機能自体には変更を加えない

    用法
    ArgumentParserの引数formatter_classにて本クラスの指定を行う
    parser = argparse.ArgumentParser(formatter_class=CustomHelpFormatter)                         
    また、本クラスの代わりに親クラス(HelpFormatter)を指定することで元のヘルプ表示が復活する
    '''

    def __init__(self, prog, indent_increment=2, max_help_position=60, width=None) -> None:
        ''' max_help_position(引数のヘルプメッセージ改行位置)を「24」から「60」に変更 
        
        以下、Lib/argparseからの抜粋
        class HelpFormatter(object):
            def __init__(self,
                         prog,
                         indent_increment=2,
                         max_help_position=24,  # 24 => 60
                         width=None):
        '''
        super().__init__(prog, indent_increment, max_help_position, width=None)


    def add_usage(self, usage, actions, groups, prefix=None) -> 'argparse.HelpFormatter':
        ''' ヘルプ内の英語表記「usage:」を日本語表記に変更 '''
        if prefix is None:
            prefix = "用法: "
    
        # 親クラス(HelpFormatter)の同名メソッド(add_usage)を自インスタンスで起動し結果を返す
        return super(CustomHelpFormatter, self).add_usage(usage, actions, groups, prefix)


    def start_section(self, heading) -> 'argparse.HelpFormatter':
        ''' ヘルプ内の英語表記「positional arguments:」,「options:」を日本語表記に変更 '''
        if heading == 'positional arguments':
            heading = '位置変数'
        elif heading == 'options':
            heading = 'オプション変数'
        return super(CustomHelpFormatter, self).start_section(heading)


    def add_argument(self, action) -> None:
        ''' コマンドラインから「'-h', '--help'」が入力された場合の英語表記を日本語表記に変更 '''
        if action.option_strings == ['-h', '--help']:
            action.help = "ヘルプ表示"
        super(CustomHelpFormatter, self).add_argument(action)


if __name__ == '__main__':
    
    parser = argparse.ArgumentParser(
                         prog='''(commonディレクトリで実行) python util.py''',
                         formatter_class=CustomHelpFormatter,
                         usage='%(prog)s [option]... [--f [file]]',
                         description='''各種ユーティリティプログラムを起動する''',
                         add_help=True, 
                        )


    parser.add_argument('-c', '--color', choices=['8', '256', '256_b',], default=False, help="ANSIカラー表示")
    parser.add_argument('-d', '--output_detail', action='store_true', default=False, help="ANSIカラー制御文字置換処理数")
    parser.add_argument('-e', '--encoding', choices=['utf_8_sig', 'utf_8', 'utf_16', 'utf_32', 'euc_jp', 'cp932', ], 
                                            default=False, help="ANSIカラー文字削除対象ファイルのencoding方式")
    parser.add_argument('--f', help="カラー文字削除対象ファイル")

    args = parser.parse_args()

    if args.color != False: 
        TerminalColor().print_ansi_color(args)

    if args.f != None:
        rm_escseq(args)