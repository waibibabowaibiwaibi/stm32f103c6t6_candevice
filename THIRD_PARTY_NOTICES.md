# Third-party notices

The MIT license in the repository root applies only to the original UART-CAN Bridge code and documentation. Third-party files retain their own copyright notices and license terms.

## STM32F1xx HAL Driver

- Location: `Drivers/STM32F1xx_HAL_Driver/`
- Upstream: STMicroelectronics STM32CubeF1
- License: the package license when distributed as part of that package; otherwise BSD-3-Clause as stated by the included notice
- Included notice: [`Drivers/STM32F1xx_HAL_Driver/LICENSE.txt`](Drivers/STM32F1xx_HAL_Driver/LICENSE.txt)

## CMSIS core headers

- Location: `Drivers/CMSIS/Include/`
- Upstream: Arm CMSIS
- License: Apache License 2.0
- Included license: [`Drivers/CMSIS/LICENSE.txt`](Drivers/CMSIS/LICENSE.txt)

## STM32F1 CMSIS device headers

- Location: `Drivers/CMSIS/Device/ST/STM32F1xx/`
- Upstream: STMicroelectronics STM32CubeF1
- License: the package license when distributed as part of that package; otherwise Apache-2.0 as stated by the included notice
- Included notice: [`Drivers/CMSIS/Device/ST/STM32F1xx/LICENSE.txt`](Drivers/CMSIS/Device/ST/STM32F1xx/LICENSE.txt)

The compiled firmware combines original project code with the components above. Redistributors should keep this file and all vendor license and copyright notices with source and binary distributions.

## STM32CubeMX-generated files

- Locations include `Core/`, `startup_stm32f103x6.s`, `STM32F103XX_FLASH.ld`, and `c6t6.ioc`
- Portions generated from STMicroelectronics templates retain the copyright and license notices embedded in those files and the applicable STM32Cube package terms
- Original code inside the generated `USER CODE` regions is covered by the project MIT license unless otherwise marked

## Windows and Linux host application dependencies

The source application depends on packages installed from Python package indexes. The current `v0.1.0-beta` Windows build was produced with:

| Component | Version | License declared by the installed package |
|---|---:|---|
| Python | 3.14.6 | Python Software Foundation License |
| PySide6 / Shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only |
| pyserial | 3.5 | BSD |
| PyInstaller | 6.22.2 | GPL-2.0-or-later with the PyInstaller bootloader exception |

New Windows and Linux builds install `PySide6-Essentials` instead of the full `PySide6` meta-package. It supplies all Qt modules used by this Widgets application; see [Qt's Essentials package inventory](https://github.com/qtproject/pyside-pyside-setup/blob/dev/README.pyside6_essentials.md). The `PySide6` import namespace and licensing remain the same. Exact package versions are pinned in `host_app/requirements-release.txt`; the Linux package records its build architecture, glibc and Python version in `BUILD-INFO.txt`.

The prebuilt application uses the LGPL-3.0 option for the dynamically loaded PySide6/Qt libraries. PySide6 wheels bundle Qt libraries. Qt for Python documents its Community Edition as LGPLv3/GPLv3 and commercial-license software; see <https://doc.qt.io/qtforpython-6/> and its license index at <https://doc.qt.io/qtforpython-6/licenses.html>. Corresponding Qt/PySide6 source releases are available from <https://download.qt.io/official_releases/QtForPython/>. Redistributors must comply with the license of every Qt module they actually bundle and preserve the user's ability to replace the dynamically loaded libraries.

Copies of the relevant license texts are included in `licenses/` and in the GitHub Release assets:

- [`licenses/LGPL-3.0.txt`](licenses/LGPL-3.0.txt) and [`licenses/GPL-3.0.txt`](licenses/GPL-3.0.txt) for PySide6/Qt
- [`licenses/PYTHON-LICENSE.txt`](licenses/PYTHON-LICENSE.txt) for the bundled Python runtime
- [`licenses/PYSERIAL-LICENSE.txt`](licenses/PYSERIAL-LICENSE.txt) for pyserial
- [`licenses/PYINSTALLER-LICENSE.txt`](licenses/PYINSTALLER-LICENSE.txt) for PyInstaller and its bootloader exception

PyInstaller is a build tool, and its bootloader exception permits distribution of applications it creates; see <https://pyinstaller.org/en/stable/license.html>.

This inventory is provided to make compliance review easier and is not legal advice. When rebuilding, inspect the metadata and licenses of the exact resolved dependency versions rather than assuming this version table is still current.
