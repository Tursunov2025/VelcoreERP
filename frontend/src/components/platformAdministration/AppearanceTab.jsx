import { useState, useEffect } from "react";

export default function AppearanceTab() {

    const [theme,setTheme]=useState("light");
    const [primaryColor,setPrimaryColor]=useState("#2563eb");
    const [sidebarColor,setSidebarColor]=useState("#111827");
    const [backgroundColor,setBackgroundColor]=useState("#f5f7fb");
    const [radius,setRadius]=useState(24);
    const [shadow,setShadow]=useState(8);
    const [fontSize,setFontSize]=useState(16);
    const [buttonHeight, setButtonHeight] = useState(45);
    useEffect(()=>{

    const saved=localStorage.getItem("velcore-theme");

    if(saved){

        const t=JSON.parse(saved);

        setPrimaryColor(t.primaryColor ?? "#2563eb");
        setSidebarColor(t.sidebarColor ?? "#111827");
        setBackgroundColor(t.backgroundColor ?? "#f5f7fb");

        setRadius(t.radius ?? 24);
        setShadow(t.shadow ?? 8);
        setFontSize(t.fontSize ?? 16);
        setButtonHeight(t.buttonHeight ?? 45);

    }

},[]);
    useEffect(()=>{

    document.documentElement.style.setProperty(
        "--erp-primary",
        primaryColor
    );

    document.documentElement.style.setProperty(
        "--erp-sidebar",
        sidebarColor
    );

    document.documentElement.style.setProperty(
        "--erp-background",
        backgroundColor
    );
    document.documentElement.style.setProperty(
        "--erp-radius",
        radius + "px"
    );

    document.documentElement.style.setProperty(
        "--erp-shadow",
        shadow + "px"
    );

    document.documentElement.style.setProperty(
        "--erp-font-size",
        fontSize + "px"
    );
    
    document.documentElement.style.setProperty(
        "--erp-button-height",
        buttonHeight + "px"
    );
},[
    primaryColor,
    sidebarColor,
    backgroundColor,
    radius,
    shadow,
    fontSize,
    buttonHeight
]);
    const saveTheme = () => {

    localStorage.setItem(
    "velcore-theme",
    JSON.stringify({
        primaryColor,
        sidebarColor,
        backgroundColor,
        radius,
        shadow,
        fontSize,
        buttonHeight
    })
);

    alert("Theme saved successfully!");
<button
    onClick={saveTheme}
    className="rounded-xl bg-blue-600 px-6 py-3 text-white font-bold hover:bg-blue-700"
>
    Save Theme
</button>
};
    return (

        <div className="space-y-6">

            <div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

                <h2 className="text-2xl font-bold">

                    Appearance Settings

                </h2>

                <p className="mt-2 text-gray-500">

                    ERP tizimining umumiy ko‘rinishini boshqarish.

                </p>

            </div>
<div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

    <h3 className="text-xl font-bold mb-5">
        Theme
    </h3>

    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">

        <button
            onClick={() => setTheme("light")}
            className={`rounded-2xl border p-4 ${
                theme === "light"
                    ? "border-blue-600 bg-blue-50"
                    : "border-gray-300"
            }`}
        >
            ☀️ Light
        </button>

        <button
            onClick={() => setTheme("dark")}
            className={`rounded-2xl border p-4 ${
                theme === "dark"
                    ? "border-blue-600 bg-blue-50"
                    : "border-gray-300"
            }`}
        >
            🌙 Dark
        </button>

    </div>
<div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

    <h3 className="text-xl font-bold mb-5">
        Color Palette
    </h3>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

        <div>
            <label className="block text-sm font-semibold mb-2">
                Primary Color
            </label>

            <input
                  type="color"
                  value={primaryColor}
                  onChange={(e)=>setPrimaryColor(e.target.value)}
                  className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Secondary Color
            </label>

            <input
                type="color"
                defaultValue="#14b8a6"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Accent Color
            </label>

            <input
                type="color"
                defaultValue="#f97316"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>
<div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

    <h3 className="text-xl font-bold mb-5">
        Sidebar Designer
    </h3>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        <div>
            <label className="block text-sm font-semibold mb-2">
                Sidebar Background
            </label>

            <input
                type="color"
                value={sidebarColor}
                onChange={(e)=>setSidebarColor(e.target.value)}
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Sidebar Text
            </label>

            <input
                type="color"
                defaultValue="#ffffff"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Active Menu Color
            </label>

            <input
                type="color"
                defaultValue="#2563eb"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Hover Color
            </label>

            <input
                type="color"
                defaultValue="#374151"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>
<div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

    <h3 className="text-xl font-bold mb-5">
        Dashboard Designer
    </h3>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        <div>
            <label className="block text-sm font-semibold mb-2">
                Dashboard Background
            </label>

            <input
                    type="color"
                    value={backgroundColor}
                    onChange={(e)=>setBackgroundColor(e.target.value)}
                    className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Card Background
            </label>

            <input
                type="color"
                defaultValue="#ffffff"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Card Radius
            </label>

            <input
                type="range"
                min="0"
                max="40"
                value={radius}
                onChange={(e)=>setRadius(Number(e.target.value))}
                className="w-full"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Shadow Size
            </label>

            <input
                 type="range"
                 min="0"
                 max="40"
                 value={shadow}
                 onChange={(e)=>setShadow(Number(e.target.value))}
                 className="w-full"
            />
        </div>
<div className="rounded-3xl border border-gray-200 bg-white p-6 shadow-sm">

    <h3 className="text-xl font-bold mb-5">
        Button Designer
    </h3>

    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

        <div>
            <label className="block text-sm font-semibold mb-2">
                Primary Button Color
            </label>

            <input
                type="color"
                defaultValue="#2563eb"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Button Text Color
            </label>

            <input
                type="color"
                defaultValue="#ffffff"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Border Radius
            </label>

            <input
                type="range"
                min="0"
                max="40"
                value={radius}
                onChange={(e) => setRadius(Number(e.target.value))}
                className="w-full"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Button Height
            </label>

            <input
                type="range"
                min="30"
                max="70"
                value={buttonHeight}
                onChange={(e) => setButtonHeight(Number(e.target.value))}
                className="w-full"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Hover Color
            </label>

            <input
                type="color"
                defaultValue="#1d4ed8"
                className="h-12 w-full rounded-xl cursor-pointer"
            />
        </div>

        <div>
            <label className="block text-sm font-semibold mb-2">
                Shadow
            </label>

            <input
                type="range"
                min="0"
                max="30"
                defaultValue="10"
                className="w-full"
            />
        </div>

    </div>

</div>
    </div>

</div>
    </div>

</div>
    </div>

</div>
</div>
              </div>

    );

}