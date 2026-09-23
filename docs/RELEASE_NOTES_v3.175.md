# SalCAPA 3.175 Release Notes

SalCAPA 3.175 preserves the reviewed PDF worker and its active-feature regression test when building the production image. The previous reconstruction step silently replaced those files with older archived copies after checkout; the 3.174 image therefore still rejected the real pending PDF despite a passing source test. The build now verifies the exact reviewed source bytes and retains them. CI also runs the PDF regression inside the built production container, including acceptance of empty annotation arrays and rejection of actual annotations and active features.

No existing original is deleted. Hash-verified promotion, archive, and automatic retry obligations remain as governed by SAL-D022. The destination SharePoint write still requires a narrowly scoped access correction and live end-to-end verification. A passing image test does not establish that real files reached the destination or archive.
