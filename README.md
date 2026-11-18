# PDF編集も自由くん

**歌詞PDFにコードを乗せられる！小節線も文字も大きさ自由自在。コードも右クリックで選べる、簡単便利なPDF編集アプリ「もじゆう君」です。**

PDFを開き、好きな位置に文字やコード、小節線を配置して、ベクター文字を保ったPDFとして保存するWindows向けアプリです。

## 起動方法

1. WindowsにPython 3.10以降をインストールします。
2. `起動.cmd` をダブルクリックします。初回は仮想環境を作成し、必要なライブラリをインストールします。
3. アプリで「PDFを開く」を選び、1ページの歌詞PDFを開きます。
4. 紙面を左クリックして文字を入力します。四隅のハンドルまたはpt欄でサイズを調整します。
5. 紙面を右クリックし、長調/短調 → キー → コードの順に選ぶと、そのコード1個をクリック位置に貼れます。
6. Ctrl+SでPDFに保存します。元のPDFへは上書きしません。

初回インストールにはインターネット接続が必要です。依存関係は `requirements.txt` に固定しています。

## 右クリックコードスタンプ

長調12キー・短調12キーのダイアトニックコードを、1コードずつ選べます。減五度コードは `Bm7-5 (Dm)` のように簡単な代理コードを括弧で示します。たとえばBm7-5の構成音B・D・F・AからルートBを省くとDm（D・F・A）になり、コードの響きは変わります。

小節線、太い小節線、複縦線、終止線、登録文字スタンプも右クリック位置に貼れます。貼った文字はドラッグで移動でき、pt単位のサイズ変更と色変更ができます。

## 対応範囲

- 1ページのPDF。複数ページPDF、パスワード付きPDF、既存の文字そのものの編集には未対応です。
- 保存後のPDFに配置文字は埋め込まれますが、次回開いた時に編集オブジェクトとしては戻りません。
- 小節線は文字グリフのスタンプです。譜表を認識して自動的に上下へ伸びる機能はありません。
- Piascoreでの実機確認はまだ行っていません。

## 開発・検証

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python src\mojiyuu.py
.venv\Scripts\python src\verify_stamps.py
```

検証済みPDF:

- [ハ長調コード個別スタンプ](samples/ハ長調コード個別スタンプ.pdf)
- [全キーの右クリックスタンプ](samples/右クリックスタンプ検証.pdf)

## ライブラリについて

PDF処理にPyMuPDF、画面にPySide6を使用します。PyMuPDFはGNU AGPL v3またはArtifex Commercial Licenseのデュアルライセンスです。PySide6はLGPL/GPLのデュアルライセンスです。各ライブラリの利用条件を確認して使用してください。

- [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright)
- [PySide6 licensing](https://doc.qt.io/qtforpython-6/licenses.html)
- [GNU AGPL v3](https://www.gnu.org/licenses/agpl-3.0.html)
