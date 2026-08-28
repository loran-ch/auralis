/** Auralis 智听 — 共享 Tailwind 配置 | livetrans_voice DESIGN.md */
document.addEventListener('click',function(e){
  var m=document.getElementById('navMenu');
  if(m&&!m.classList.contains('hidden')&&!e.target.closest('#navMenu')&&!e.target.closest('button[onclick*="navMenu"]')){
    m.classList.add('hidden');
  }
});
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary":"#005ea1","on-primary":"#ffffff","primary-container":"#2b78bf","on-primary-container":"#fdfcff",
        "secondary":"#006e1c","on-secondary":"#ffffff","secondary-container":"#91f78e",
        "tertiary":"#874e00","on-tertiary":"#ffffff","tertiary-container":"#aa6400","tertiary-fixed":"#ffdcbe",
        "error":"#ba1a1a","error-container":"#ffdad6","on-error-container":"#93000a",
        "ink-deep":"#1A1A1A","ink-subdued":"#8B8B8B","success-dim":"rgba(76,175,80,0.6)",
        "alert-red":"#EF4444","accent-purple":"#8B5CF6",
        "surface":"#faf9fa","surface-dim":"#dadadb","surface-bright":"#faf9fa",
        "surface-container-lowest":"#ffffff","surface-container-low":"#f4f3f4",
        "surface-container":"#eeedee","surface-container-high":"#e9e8e9","surface-container-highest":"#e3e2e3",
        "surface-variant":"#e3e2e3","on-surface":"#1a1c1d","on-surface-variant":"#414751",
        "on-background":"#1a1c1d","background":"#faf9fa","outline":"#717782","outline-variant":"#c1c7d2",
        "inverse-surface":"#2f3032","inverse-on-surface":"#f1f0f1","surface-tint":"#0061a5"
      },
      borderRadius: {"sm":"0.25rem","DEFAULT":"0.5rem","md":"0.75rem","lg":"1rem","xl":"1.5rem","full":"9999px"},
      fontFamily: {"headline":["Inter"],"display":["Inter"],"body":["Inter"],"label":["Inter"]},
      spacing: {"unit":"4px","gutter":"16px","stack-sm":"8px","stack-md":"16px","stack-lg":"24px","margin-mobile":"20px","margin-desktop":"40px"}
    }
  }
};
