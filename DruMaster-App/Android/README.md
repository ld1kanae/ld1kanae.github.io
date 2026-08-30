# DruMaster Android package

DruMaster Web本体を変更せず、CapacitorでAndroidアプリ化するためのラッパーです。

## 構成

- Web本体: `../../DruMaster/`
- Androidパッケージ: このディレクトリ
- Capacitor `webDir`: `www/`（生成物・Git管理外）
- アプリアイコン原本: `assets/icon.svg`
  - `DruMaster/assets/DruMaster-D-white.svg` と同じD単体ロゴ

## 初回生成

```bash
npm install
npm run android:add
npm run android:icons
npm run android:sync
npm run android:open
```

`npm run sync:web` は、その時点の最新 `DruMaster/` を `www/` へコピーします。

通常のWeb更新後は以下でAndroid側へ反映します。

```bash
npm run android:sync
```

Android StudioからDebug APKを生成できます。

## 方針

- Web版のソースをAndroid用に書き換えない。
- `www/` と生成された `android/` はビルド生成物としてGit管理しない。
- 内部リソースはWeb版と同じ相対パスを使用する。
- 外部API等の絶対URLはそのまま維持する。
