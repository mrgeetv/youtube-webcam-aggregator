# Changelog

All notable changes to this project will be documented in this file. See [Conventional Commits](https://conventionalcommits.org) for commit guidelines.

## [1.1.6](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.5...v1.1.6) (2026-01-27)

### Bug Fixes

* **deps:** bump actions/checkout from 6.0.1 to 6.0.2 ([#34](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/34)) ([ae6401c](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/ae6401c5e2b39059bb3e7bf300e3b236db0646f8))
* **deps:** bump actions/setup-python from 6.1.0 to 6.2.0 ([#32](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/32)) ([8df1620](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/8df1620d254a11c4e3fc5210024fe4418e51776d))
* **deps:** bump the python-dependencies group with 3 updates ([#31](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/31)) ([7d39eef](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/7d39eef392b97cf192bc842af904f85de38d9a3b))

## [1.1.5](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.4...v1.1.5) (2026-01-02)

### Bug Fixes

* **deps:** bump docker/setup-buildx-action from 3.11.1 to 3.12.0 ([#28](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/28)) ([31243fc](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/31243fc34aebcfe645448b335e81e5a7724c58c9))
* **deps:** bump the python-dependencies group across 1 directory with 2 updates ([#30](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/30)) ([3f5db49](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/3f5db4935a028266e0dad5ccf7049c2051d83599))

## [1.1.4](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.3...v1.1.4) (2025-12-19)

### Bug Fixes

* **deps:** bump the python-dependencies group with 2 updates ([#25](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/25)) ([5f293b6](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/5f293b60d25bfa4f91f214009cebd89e1b707bb4))

### Performance Improvements

* **scraper:** parallelize stream extraction with ThreadPoolExecutor ([#26](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/26)) ([6cf6087](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/6cf6087f67530e73252549e6a155dc05aa0f4624))

## [1.1.3](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.2...v1.1.3) (2025-12-18)

### Bug Fixes

* **docker:** secure HTTP handler and add health endpoint ([#24](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/24)) ([84011ad](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/84011adaf26294782a91a4b6fc999f374a015f2c))

## [1.1.2](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.1...v1.1.2) (2025-12-18)

### Bug Fixes

* **api:** add retry with exponential backoff for transient errors ([#23](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/23)) ([2d26e4e](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/2d26e4eb867c33819d097417ae0e820a38ecdb43))

## [1.1.1](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.1.0...v1.1.1) (2025-12-18)

### Bug Fixes

* **scraper:** add memory management to prevent growth across cycles ([#22](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/22)) ([ca91436](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/ca914367932d7c68331d69d3c25fe00454c65735))

## [1.1.0](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.7...v1.1.0) (2025-12-17)


### Features

* **docker:** migrate to Docker Hardened Images with multi-stage build ([#20](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/20)) ([02beec5](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/02beec540c1382c9d9c38f299389eae508cb82f3))

## [1.0.7](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.6...v1.0.7) (2025-12-13)


### Bug Fixes

* **deps:** bump actions/cache from 4.3.0 to 5.0.1 ([#15](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/15)) ([9e015bb](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/9e015bb4ef0985bc307f17acc712f1f136e0dbd1))
* **deps:** bump hadolint/hadolint-action from 3.1.0 to 3.3.0 ([#16](https://github.com/mrgeetv/youtube-webcam-aggregator/issues/16)) ([e0d570d](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/e0d570d62d1c17f1810b963829842d119b874ba3))

## [1.0.6](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.5...v1.0.6) (2025-12-13)


### Bug Fixes

* **scraper:** use yt-dlp subprocess to prevent memory leak ([f21bc07](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/f21bc07f928a89f491a102fa5df350f22d38fbbe))

## [1.0.5](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.4...v1.0.5) (2025-12-12)


### Bug Fixes

* **deps:** bump yt-dlp in the python-dependencies group ([3b2c9b2](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/3b2c9b27ceb76ecc9aa65991d7cc09e985f4c696))

## [1.0.4](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.3...v1.0.4) (2025-12-05)


### Bug Fixes

* **docker:** add --no-cache-dir flag to pip install ([7e27a5b](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/7e27a5b7656ac1a0d1c0fed373bae49cc63c9ead))
* **docker:** pin Python version to 3.14-slim ([a96eda4](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/a96eda40143f876d6852fa3b086aff561252b41a))

## [1.0.3](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.2...v1.0.3) (2025-12-05)


### Bug Fixes

* **deps:** restore version pinning in requirements.txt ([cb7019f](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/cb7019f41400afae55db2a03cbaea5b6765e8d2c))
* **docker:** add Deno runtime for yt-dlp YouTube extraction ([cf06b4c](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/cf06b4ce091e2b176f8dfc4b00a6c1d4a9671228))

## [1.0.2](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.1...v1.0.2) (2025-12-05)


### Bug Fixes

* **deps:** bump actions/cache from 4.2.3 to 4.3.0 ([e1184f4](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/e1184f49ee3f4c639867a403a37d980209c17bb9))
* **deps:** bump actions/checkout from 4.2.2 to 6.0.1 ([b124b0b](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/b124b0b53f6302bfaa5f0396e97fea5faa82ffac))
* **deps:** bump actions/setup-python from 5.6.0 to 6.1.0 ([4614d57](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/4614d5785901a3b7e056ac0a9c37d5dc3ae29dc3))
* **deps:** bump cycjimmy/semantic-release-action from 4.2.2 to 6.0.0 ([1585263](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/1585263bdbde81e7fb7071aec6102285b3fa3689))
* **deps:** bump docker/login-action from 3.4.0 to 3.6.0 ([8b01de1](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/8b01de158b1485831889703243549f8e250a991a))

## [1.0.1](https://github.com/mrgeetv/youtube-webcam-aggregator/compare/v1.0.0...v1.0.1) (2025-12-05)


### Bug Fixes

* **ci:** exclude auto-generated CHANGELOG.md from markdownlint ([c558846](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/c5588463a779d6d7af1d5685320353277a153e2c))

## 1.0.0 (2025-12-05)


### Bug Fixes

* **ci:** remove duplicate workflow trigger in ci.yml ([33b775e](https://github.com/mrgeetv/youtube-webcam-aggregator/commit/33b775efb875f14fac8b21303c7636e0d21a08eb))
