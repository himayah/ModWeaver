@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem ------------------------------------------------------------------
rem DESIGN.md 第11章の「試聴で調整する項目」を確かめるための曲を、項目ごとに3例ずつ作る。
rem 出力先: output\listen\<番号_項目>\<ジャンル>_<シード>.<拡張子>（output\ は .gitignore 済み）。
rem   14_arrangements だけは <ジャンル>_<シード>_<チャンネル数>ch.<拡張子>（同じ曲を編成ごとに聴き比べる）。
rem 使い方: リポジトリ直下でこのファイルを実行する（ダブルクリックでも可）。
rem   PY  : Python の起動コマンド（例: py -3）
rem   FMT : 出力形式（mod / xm / s3m / it / midi / mp3。mp3 は ffmpeg が必要）
rem   EXT : FMT に対応する拡張子（midi のときは mid）
rem シードは 101, 202, 303（同じシードなら何度作っても同じ曲）。
rem ------------------------------------------------------------------
cd /d "%~dp0"
if "%PY%"=="" set "PY=python"
if "%FMT%"=="" set "FMT=mod"
if "%EXT%"=="" set "EXT=%FMT%"
if /i "%FMT%"=="midi" set "EXT=mid"
set /a OK=0
set /a NG=0

echo [01_swing-jazz] swing-jazz のスウィング比 - 14:10 のハネ具合
call :gen 01_swing-jazz swing-jazz 101
call :gen 01_swing-jazz swing-jazz 202
call :gen 01_swing-jazz swing-jazz 303

echo [02_trap] trap のロール確率・808 グライド速度 - ハイハットのロールの多さ、808 のグライドの速さ
call :gen 02_trap trap 101
call :gen 02_trap trap 202
call :gen 02_trap trap 303

echo [03_future-bass] future-bass のダッキング - キックに合わせたベースと和音のうねりの深さ・戻り
call :gen 03_future-bass future-bass 101
call :gen 03_future-bass future-bass 202
call :gen 03_future-bass future-bass 303

echo [04_maqam] maqam の旋律の跳躍確率 - ウードの旋律の跳躍の多さ
call :gen 04_maqam maqam 101
call :gen 04_maqam maqam 202
call :gen 04_maqam maqam 303

echo [05_minimalism] minimalism の音型 - 4つの固定音型のずれと戻り
call :gen 05_minimalism minimalism 101
call :gen 05_minimalism minimalism 202
call :gen 05_minimalism minimalism 303

echo [06_free-jazz] free-jazz の密度 - ベース・ピアノ・打楽器・サックスの音の密度
call :gen 06_free-jazz free-jazz 101
call :gen 06_free-jazz free-jazz 202
call :gen 06_free-jazz free-jazz 303

echo [07_orchestral] orchestral のボイシング・音量変化 - 6声の重なりと区間ごとの音量の変化
call :gen 07_orchestral orchestral 101
call :gen 07_orchestral orchestral 202
call :gen 07_orchestral orchestral 303

echo [08_prog-rock] prog-rock の lead のビブラート - リードギターにビブラートが要るか
call :gen 08_prog-rock prog-rock 101
call :gen 08_prog-rock prog-rock 202
call :gen 08_prog-rock prog-rock 303

echo [09_nostalgic] nostalgic の pad の −17.6 セント - パッドとオルゴールのわずかなうなり
call :gen 09_nostalgic nostalgic 101
call :gen 09_nostalgic nostalgic 202
call :gen 09_nostalgic nostalgic 303

echo [10_stage3-balance] 第３段階の35ジャンルの音量・音色の釣り合い - 各ジャンルのパートの音量と音色の釣り合い（ジャンルごとに3例）
call :gen 10_stage3-balance acoustic-ssw 101
call :gen 10_stage3-balance acoustic-ssw 202
call :gen 10_stage3-balance acoustic-ssw 303
call :gen 10_stage3-balance ambient 101
call :gen 10_stage3-balance ambient 202
call :gen 10_stage3-balance ambient 303
call :gen 10_stage3-balance ambient-drone 101
call :gen 10_stage3-balance ambient-drone 202
call :gen 10_stage3-balance ambient-drone 303
call :gen 10_stage3-balance anime-ost 101
call :gen 10_stage3-balance anime-ost 202
call :gen 10_stage3-balance anime-ost 303
call :gen 10_stage3-balance bossa-nova 101
call :gen 10_stage3-balance bossa-nova 202
call :gen 10_stage3-balance bossa-nova 303
call :gen 10_stage3-balance calm 101
call :gen 10_stage3-balance calm 202
call :gen 10_stage3-balance calm 303
call :gen 10_stage3-balance cinematic 101
call :gen 10_stage3-balance cinematic 202
call :gen 10_stage3-balance cinematic 303
call :gen 10_stage3-balance city-pop 101
call :gen 10_stage3-balance city-pop 202
call :gen 10_stage3-balance city-pop 303
call :gen 10_stage3-balance classical 101
call :gen 10_stage3-balance classical 202
call :gen 10_stage3-balance classical 303
call :gen 10_stage3-balance cool 101
call :gen 10_stage3-balance cool 202
call :gen 10_stage3-balance cool 303
call :gen 10_stage3-balance dark-tense 101
call :gen 10_stage3-balance dark-tense 202
call :gen 10_stage3-balance dark-tense 303
call :gen 10_stage3-balance dreamy 101
call :gen 10_stage3-balance dreamy 202
call :gen 10_stage3-balance dreamy 303
call :gen 10_stage3-balance edm 101
call :gen 10_stage3-balance edm 202
call :gen 10_stage3-balance edm 303
call :gen 10_stage3-balance energetic 101
call :gen 10_stage3-balance energetic 202
call :gen 10_stage3-balance energetic 303
call :gen 10_stage3-balance focus 101
call :gen 10_stage3-balance focus 202
call :gen 10_stage3-balance focus 303
call :gen 10_stage3-balance folk 101
call :gen 10_stage3-balance folk 202
call :gen 10_stage3-balance folk 303
call :gen 10_stage3-balance hiphop 101
call :gen 10_stage3-balance hiphop 202
call :gen 10_stage3-balance hiphop 303
call :gen 10_stage3-balance house 101
call :gen 10_stage3-balance house 202
call :gen 10_stage3-balance house 303
call :gen 10_stage3-balance indie-rock 101
call :gen 10_stage3-balance indie-rock 202
call :gen 10_stage3-balance indie-rock 303
call :gen 10_stage3-balance jazz 101
call :gen 10_stage3-balance jazz 202
call :gen 10_stage3-balance jazz 303
call :gen 10_stage3-balance jpop-80s 101
call :gen 10_stage3-balance jpop-80s 202
call :gen 10_stage3-balance jpop-80s 303
call :gen 10_stage3-balance jrock-90s 101
call :gen 10_stage3-balance jrock-90s 202
call :gen 10_stage3-balance jrock-90s 303
call :gen 10_stage3-balance jrpg 101
call :gen 10_stage3-balance jrpg 202
call :gen 10_stage3-balance jrpg 303
call :gen 10_stage3-balance lofi-chill 101
call :gen 10_stage3-balance lofi-chill 202
call :gen 10_stage3-balance lofi-chill 303
call :gen 10_stage3-balance lofi-hiphop 101
call :gen 10_stage3-balance lofi-hiphop 202
call :gen 10_stage3-balance lofi-hiphop 303
call :gen 10_stage3-balance melancholic 101
call :gen 10_stage3-balance melancholic 202
call :gen 10_stage3-balance melancholic 303
call :gen 10_stage3-balance neo-soul 101
call :gen 10_stage3-balance neo-soul 202
call :gen 10_stage3-balance neo-soul 303
call :gen 10_stage3-balance pop 101
call :gen 10_stage3-balance pop 202
call :gen 10_stage3-balance pop 303
call :gen 10_stage3-balance rnb-soul 101
call :gen 10_stage3-balance rnb-soul 202
call :gen 10_stage3-balance rnb-soul 303
call :gen 10_stage3-balance rock 101
call :gen 10_stage3-balance rock 202
call :gen 10_stage3-balance rock 303
call :gen 10_stage3-balance synthwave 101
call :gen 10_stage3-balance synthwave 202
call :gen 10_stage3-balance synthwave 303
call :gen 10_stage3-balance techno 101
call :gen 10_stage3-balance techno 202
call :gen 10_stage3-balance techno 303
call :gen 10_stage3-balance trailer 101
call :gen 10_stage3-balance trailer 202
call :gen 10_stage3-balance trailer 303
call :gen 10_stage3-balance uplifting 101
call :gen 10_stage3-balance uplifting 202
call :gen 10_stage3-balance uplifting 303
call :gen 10_stage3-balance warm 101
call :gen 10_stage3-balance warm 202
call :gen 10_stage3-balance warm 303

echo [11_folk] folk の前打音の確率 - フィドルの前打音の多さ
call :gen 11_folk folk 101
call :gen 11_folk folk 202
call :gen 11_folk folk 303

echo [12_neo-soul] neo-soul の「よれ」の確率 - スネアとハットの遅れ具合
call :gen 12_neo-soul neo-soul 101
call :gen 12_neo-soul neo-soul 202
call :gen 12_neo-soul neo-soul 303

echo [13_jrpg] jrpg のゼクエンツ - 旋律の2小節目が1音上がる反復と、音域の上端での頭打ち
call :gen 13_jrpg jrpg 101
call :gen 13_jrpg jrpg 202
call :gen 13_jrpg jrpg 303

echo [14_arrangements] 曲ごとの編成（4ch で省くパート・8ch で足す任意パート） - 同じシードの曲を編成ごとに聴き比べる（ジャンルごとに3例 × 選べる編成）
call :gen 14_arrangements acoustic-ssw 101 4
call :gen 14_arrangements acoustic-ssw 101 6
call :gen 14_arrangements acoustic-ssw 202 4
call :gen 14_arrangements acoustic-ssw 202 6
call :gen 14_arrangements acoustic-ssw 303 4
call :gen 14_arrangements acoustic-ssw 303 6
call :gen 14_arrangements anime-ost 101 4
call :gen 14_arrangements anime-ost 101 6
call :gen 14_arrangements anime-ost 101 8
call :gen 14_arrangements anime-ost 202 4
call :gen 14_arrangements anime-ost 202 6
call :gen 14_arrangements anime-ost 202 8
call :gen 14_arrangements anime-ost 303 4
call :gen 14_arrangements anime-ost 303 6
call :gen 14_arrangements anime-ost 303 8
call :gen 14_arrangements bossa-nova 101 4
call :gen 14_arrangements bossa-nova 101 6
call :gen 14_arrangements bossa-nova 202 4
call :gen 14_arrangements bossa-nova 202 6
call :gen 14_arrangements bossa-nova 303 4
call :gen 14_arrangements bossa-nova 303 6
call :gen 14_arrangements cinematic 101 6
call :gen 14_arrangements cinematic 101 8
call :gen 14_arrangements cinematic 202 6
call :gen 14_arrangements cinematic 202 8
call :gen 14_arrangements cinematic 303 6
call :gen 14_arrangements cinematic 303 8
call :gen 14_arrangements city-pop 101 4
call :gen 14_arrangements city-pop 101 6
call :gen 14_arrangements city-pop 101 8
call :gen 14_arrangements city-pop 202 4
call :gen 14_arrangements city-pop 202 6
call :gen 14_arrangements city-pop 202 8
call :gen 14_arrangements city-pop 303 4
call :gen 14_arrangements city-pop 303 6
call :gen 14_arrangements city-pop 303 8
call :gen 14_arrangements cool 101 4
call :gen 14_arrangements cool 101 6
call :gen 14_arrangements cool 101 8
call :gen 14_arrangements cool 202 4
call :gen 14_arrangements cool 202 6
call :gen 14_arrangements cool 202 8
call :gen 14_arrangements cool 303 4
call :gen 14_arrangements cool 303 6
call :gen 14_arrangements cool 303 8
call :gen 14_arrangements dark-tense 101 4
call :gen 14_arrangements dark-tense 101 6
call :gen 14_arrangements dark-tense 101 8
call :gen 14_arrangements dark-tense 202 4
call :gen 14_arrangements dark-tense 202 6
call :gen 14_arrangements dark-tense 202 8
call :gen 14_arrangements dark-tense 303 4
call :gen 14_arrangements dark-tense 303 6
call :gen 14_arrangements dark-tense 303 8
call :gen 14_arrangements dreamy 101 4
call :gen 14_arrangements dreamy 101 6
call :gen 14_arrangements dreamy 101 8
call :gen 14_arrangements dreamy 202 4
call :gen 14_arrangements dreamy 202 6
call :gen 14_arrangements dreamy 202 8
call :gen 14_arrangements dreamy 303 4
call :gen 14_arrangements dreamy 303 6
call :gen 14_arrangements dreamy 303 8
call :gen 14_arrangements edm 101 4
call :gen 14_arrangements edm 101 6
call :gen 14_arrangements edm 101 8
call :gen 14_arrangements edm 202 4
call :gen 14_arrangements edm 202 6
call :gen 14_arrangements edm 202 8
call :gen 14_arrangements edm 303 4
call :gen 14_arrangements edm 303 6
call :gen 14_arrangements edm 303 8
call :gen 14_arrangements energetic 101 4
call :gen 14_arrangements energetic 101 6
call :gen 14_arrangements energetic 101 8
call :gen 14_arrangements energetic 202 4
call :gen 14_arrangements energetic 202 6
call :gen 14_arrangements energetic 202 8
call :gen 14_arrangements energetic 303 4
call :gen 14_arrangements energetic 303 6
call :gen 14_arrangements energetic 303 8
call :gen 14_arrangements folk 101 4
call :gen 14_arrangements folk 101 6
call :gen 14_arrangements folk 202 4
call :gen 14_arrangements folk 202 6
call :gen 14_arrangements folk 303 4
call :gen 14_arrangements folk 303 6
call :gen 14_arrangements hiphop 101 4
call :gen 14_arrangements hiphop 101 6
call :gen 14_arrangements hiphop 202 4
call :gen 14_arrangements hiphop 202 6
call :gen 14_arrangements hiphop 303 4
call :gen 14_arrangements hiphop 303 6
call :gen 14_arrangements house 101 4
call :gen 14_arrangements house 101 6
call :gen 14_arrangements house 101 8
call :gen 14_arrangements house 202 4
call :gen 14_arrangements house 202 6
call :gen 14_arrangements house 202 8
call :gen 14_arrangements house 303 4
call :gen 14_arrangements house 303 6
call :gen 14_arrangements house 303 8
call :gen 14_arrangements indie-rock 101 4
call :gen 14_arrangements indie-rock 101 6
call :gen 14_arrangements indie-rock 101 8
call :gen 14_arrangements indie-rock 202 4
call :gen 14_arrangements indie-rock 202 6
call :gen 14_arrangements indie-rock 202 8
call :gen 14_arrangements indie-rock 303 4
call :gen 14_arrangements indie-rock 303 6
call :gen 14_arrangements indie-rock 303 8
call :gen 14_arrangements jpop-80s 101 4
call :gen 14_arrangements jpop-80s 101 6
call :gen 14_arrangements jpop-80s 101 8
call :gen 14_arrangements jpop-80s 202 4
call :gen 14_arrangements jpop-80s 202 6
call :gen 14_arrangements jpop-80s 202 8
call :gen 14_arrangements jpop-80s 303 4
call :gen 14_arrangements jpop-80s 303 6
call :gen 14_arrangements jpop-80s 303 8
call :gen 14_arrangements jrock-90s 101 4
call :gen 14_arrangements jrock-90s 101 6
call :gen 14_arrangements jrock-90s 101 8
call :gen 14_arrangements jrock-90s 202 4
call :gen 14_arrangements jrock-90s 202 6
call :gen 14_arrangements jrock-90s 202 8
call :gen 14_arrangements jrock-90s 303 4
call :gen 14_arrangements jrock-90s 303 6
call :gen 14_arrangements jrock-90s 303 8
call :gen 14_arrangements jrpg 101 4
call :gen 14_arrangements jrpg 101 6
call :gen 14_arrangements jrpg 101 8
call :gen 14_arrangements jrpg 202 4
call :gen 14_arrangements jrpg 202 6
call :gen 14_arrangements jrpg 202 8
call :gen 14_arrangements jrpg 303 4
call :gen 14_arrangements jrpg 303 6
call :gen 14_arrangements jrpg 303 8
call :gen 14_arrangements lofi-chill 101 4
call :gen 14_arrangements lofi-chill 101 6
call :gen 14_arrangements lofi-chill 101 8
call :gen 14_arrangements lofi-chill 202 4
call :gen 14_arrangements lofi-chill 202 6
call :gen 14_arrangements lofi-chill 202 8
call :gen 14_arrangements lofi-chill 303 4
call :gen 14_arrangements lofi-chill 303 6
call :gen 14_arrangements lofi-chill 303 8
call :gen 14_arrangements lofi-hiphop 101 4
call :gen 14_arrangements lofi-hiphop 101 6
call :gen 14_arrangements lofi-hiphop 101 8
call :gen 14_arrangements lofi-hiphop 202 4
call :gen 14_arrangements lofi-hiphop 202 6
call :gen 14_arrangements lofi-hiphop 202 8
call :gen 14_arrangements lofi-hiphop 303 4
call :gen 14_arrangements lofi-hiphop 303 6
call :gen 14_arrangements lofi-hiphop 303 8
call :gen 14_arrangements neo-soul 101 4
call :gen 14_arrangements neo-soul 101 6
call :gen 14_arrangements neo-soul 101 8
call :gen 14_arrangements neo-soul 202 4
call :gen 14_arrangements neo-soul 202 6
call :gen 14_arrangements neo-soul 202 8
call :gen 14_arrangements neo-soul 303 4
call :gen 14_arrangements neo-soul 303 6
call :gen 14_arrangements neo-soul 303 8
call :gen 14_arrangements pop 101 4
call :gen 14_arrangements pop 101 6
call :gen 14_arrangements pop 101 8
call :gen 14_arrangements pop 202 4
call :gen 14_arrangements pop 202 6
call :gen 14_arrangements pop 202 8
call :gen 14_arrangements pop 303 4
call :gen 14_arrangements pop 303 6
call :gen 14_arrangements pop 303 8
call :gen 14_arrangements rnb-soul 101 4
call :gen 14_arrangements rnb-soul 101 6
call :gen 14_arrangements rnb-soul 101 8
call :gen 14_arrangements rnb-soul 202 4
call :gen 14_arrangements rnb-soul 202 6
call :gen 14_arrangements rnb-soul 202 8
call :gen 14_arrangements rnb-soul 303 4
call :gen 14_arrangements rnb-soul 303 6
call :gen 14_arrangements rnb-soul 303 8
call :gen 14_arrangements rock 101 4
call :gen 14_arrangements rock 101 6
call :gen 14_arrangements rock 101 8
call :gen 14_arrangements rock 202 4
call :gen 14_arrangements rock 202 6
call :gen 14_arrangements rock 202 8
call :gen 14_arrangements rock 303 4
call :gen 14_arrangements rock 303 6
call :gen 14_arrangements rock 303 8
call :gen 14_arrangements synthwave 101 4
call :gen 14_arrangements synthwave 101 6
call :gen 14_arrangements synthwave 101 8
call :gen 14_arrangements synthwave 202 4
call :gen 14_arrangements synthwave 202 6
call :gen 14_arrangements synthwave 202 8
call :gen 14_arrangements synthwave 303 4
call :gen 14_arrangements synthwave 303 6
call :gen 14_arrangements synthwave 303 8
call :gen 14_arrangements trailer 101 6
call :gen 14_arrangements trailer 101 8
call :gen 14_arrangements trailer 202 6
call :gen 14_arrangements trailer 202 8
call :gen 14_arrangements trailer 303 6
call :gen 14_arrangements trailer 303 8
call :gen 14_arrangements uplifting 101 4
call :gen 14_arrangements uplifting 101 6
call :gen 14_arrangements uplifting 101 8
call :gen 14_arrangements uplifting 202 4
call :gen 14_arrangements uplifting 202 6
call :gen 14_arrangements uplifting 202 8
call :gen 14_arrangements uplifting 303 4
call :gen 14_arrangements uplifting 303 6
call :gen 14_arrangements uplifting 303 8
call :gen 14_arrangements warm 101 4
call :gen 14_arrangements warm 101 6
call :gen 14_arrangements warm 202 4
call :gen 14_arrangements warm 202 6
call :gen 14_arrangements warm 303 4
call :gen 14_arrangements warm 303 6

echo [15_new-genres] gamelan・chiptune・industrial の音量・音色 - ガムランの音律と装飾の密度、チップチューンのアルペジオとジャンプ音、インダストリアルの歪み（ジャンルごとに3例）
call :gen 15_new-genres gamelan 101
call :gen 15_new-genres gamelan 202
call :gen 15_new-genres gamelan 303
call :gen 15_new-genres chiptune 101
call :gen 15_new-genres chiptune 202
call :gen 15_new-genres chiptune 303
call :gen 15_new-genres industrial 101
call :gen 15_new-genres industrial 202
call :gen 15_new-genres industrial 303

echo.
echo 完了: 成功 !OK! 件、失敗 !NG! 件（全 372 件）。出力先: output\listen\
pause
exit /b 0

:gen
rem 引数: 1=フォルダ 2=ジャンル 3=シード 4=チャンネル数（省略可。省略時はジャンルが選ぶ）
if not exist "output\listen\%~1" mkdir "output\listen\%~1"
if "%~4"=="" (
    %PY% modweaver.py --genre %~2 --seed %~3 --format %FMT% --output "output\listen\%~1\%~2_%~3.%EXT%" >nul
) else (
    %PY% modweaver.py --genre %~2 --seed %~3 --channels %~4 --format %FMT% --output "output\listen\%~1\%~2_%~3_%~4ch.%EXT%" >nul
)
if errorlevel 1 (
    echo   失敗: %~2 seed %~3
    set /a NG+=1
) else (
    set /a OK+=1
)
exit /b 0
