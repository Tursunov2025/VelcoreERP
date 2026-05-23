
import { useEffect, useState } from "react";
function App() {
  const [showModal, setShowModal] = useState(false);
const [isLoggedIn, setIsLoggedIn] = useState(false);

const [loginUser, setLoginUser] = useState("");

const [loginPassword, setLoginPassword] = useState("");
  const [client, setClient] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
const [editModal, setEditModal] = useState(false);

const [editId, setEditId] = useState(null);

const [editClient, setEditClient] = useState("");

const [editPhone, setEditPhone] = useState("");

const [editAmount, setEditAmount] = useState("");
  const [orders, setOrders] = useState([]);
const [search, setSearch] = useState("");
  const totalOrders = orders.length;

  const completedOrders = orders.filter(
    (item) => item.status === "Tayyor"
  ).length;

  const activeOrders = orders.filter(
    (item) => item.status !== "Tayyor"
  ).length;

  const totalAmount = orders.reduce((sum, item) => {
    return sum + Number(item.amount || 0);
  }, 0);

  useEffect(() => {

    fetch("https://azmus-crm.onrender.com/orders")
      .then((res) => res.json())
      .then((data) => {
        setOrders(data);
      });

  }, []);

  const addOrder = async () => {

    if (!client || !amount) {
      return;
    }

    const response = await fetch(
      "https://azmus-crm.onrender.com/orders",
      {

        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          client,
          phone,
          amount,
        }),

      }
    );

    const data = await response.json();

    setOrders([...orders, data]);

    setClient("");
    setPhone("");
    setAmount("");

    setShowModal(false);

  };
if (!isLoggedIn) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f5f6fa]">

      <div className="bg-white w-[450px] rounded-[40px] p-10 shadow-2xl">

        <h1 className="text-4xl font-black mb-8 text-center">
          Azmus CRM
        </h1>

        <div className="space-y-5">

          <input
            value={loginUser}
            onChange={(e) => setLoginUser(e.target.value)}
            placeholder="Login"
            className="w-full border rounded-2xl px-5 py-4"
          />

          <input
            type="password"
            value={loginPassword}
            onChange={(e) => setLoginPassword(e.target.value)}
            placeholder="Parol"
            className="w-full border rounded-2xl px-5 py-4"
          />

          <button

            onClick={async () => {

              const res = await fetch(
                "https://azmus-crm.onrender.com/login",
                {
                  method: "POST",
                  headers: {
                    "Content-Type": "application/json"
                  },
                  body: JSON.stringify({
                    username: loginUser,
                    password: loginPassword
                  })
                }
              )

              const data = await res.json()

              if (data.success) {

                setIsLoggedIn(true)

              } else {

                alert("Login yoki parol xato")

              }

            }}

            className="w-full bg-black text-white py-4 rounded-2xl font-bold"
          >
            Kirish
          </button>

        </div>

      </div>

    </div>
  )
}
  return (

    <div className="min-h-screen bg-[#f5f6fa] flex">

      <div className="w-[90px] md:w-[260px] bg-black text-white p-6 rounded-r-[40px] shadow-2xl">

        <h1 className="text-2xl md:text-5xl font-black mb-14 tracking-tight leading-tight">
  Azmus furniture
</h1>

        <div className="space-y-5 mt-10">

          <span className="hidden md:block">
  Dashboard
</span>

          <span className="hidden md:block">
  Zakazlar
</span>

          <span className="hidden md:block">
  Ishlab chiqarish
</span>

          <span className="hidden md:block">
  Ombor
</span>

        </div>

      </div>

      <div className="flex-1 p-4 md:p-6 lg:p-10">

        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 mb-8">

          <div className="bg-white rounded-[32px] p-6 shadow-lg">
            <p className="text-gray-500">
              Jami Zakaz
            </p>

            <h1 className="text-4xl font-black mt-3">
              {totalOrders}
            </h1>
          </div>

          <div className="bg-green-500 text-white rounded-[32px] p-6 shadow-lg">
            <p>
              Tayyor
            </p>

            <h1 className="text-4xl font-black mt-3">
              {completedOrders}
            </h1>
          </div>

          <div className="bg-yellow-500 text-white rounded-[32px] p-6 shadow-lg">
            <p>
              Ishlab chiqarishda
            </p>

            <h1 className="text-4xl font-black mt-3">
              {activeOrders}
            </h1>
          </div>

          <div className="bg-black text-white rounded-[32px] p-6 shadow-lg">
            <p>
              Umumiy Summa
            </p>

            <h1 className="text-4xl font-black mt-3">
              {totalAmount.toLocaleString()} so'm
            </h1>
          </div>

        </div>

        <div className="bg-white rounded-[40px] shadow-xl p-8">

          <div className="flex flex-col xl:flex-row xl:items-center justify-between gap-6 mb-8">

  <div className="w-full xl:w-auto">

    <input

      value={search}

      onChange={(e) => setSearch(e.target.value)}

      placeholder="Qidirish..."

      className="w-full xl:w-[420px] border border-gray-300 rounded-[20px] px-5 py-4 outline-none focus:ring-2 focus:ring-black"

    />

  </div>

  <div className="flex flex-wrap items-center gap-3">

    <h2 className="text-2xl md:text-3xl font-black mr-2">
      Zakazlar
    </h2>

    <button

      onClick={() => {

        setIsLoggedIn(false);

      }}

      className="bg-red-500 hover:bg-red-600 transition-all text-white px-6 py-3 rounded-[20px] shadow-lg"
    >
      Chiqish
    </button>

    <button

      onClick={() => setShowModal(true)}

      className="bg-black hover:bg-gray-800 transition-all text-white px-6 py-3 rounded-[20px] shadow-lg"
    >
      + Yangi Zakaz
    </button>

  </div>

</div>

          <div className="space-y-5">

            {orders

.filter((order) => {

  return (

    order.client
      .toLowerCase()
      .includes(search.toLowerCase())

    ||

    order.status
      .toLowerCase()
      .includes(search.toLowerCase())

    ||

    String(order.amount)
      .includes(search)

  );

})

.map((order, index) => (

              <div
                key={index}
                className="border border-gray-200 rounded-[28px] p-6 flex flex-col xl:flex-row xl:items-center justify-between gap-6 hover:shadow-lg transition-all"
              >

                <div>
                  <h3 className="font-bold text-xl">
                    {order.id}
                  </h3>

                  <p className="text-gray-500 mt-2">
                    {order.client}
                  </p>
                </div>

                <select
                  value={order.status}
                  onChange={async (e) => {

  const newStatus = e.target.value;

  const updated = [...orders];

  updated[index].status = newStatus;

  setOrders(updated);

  await fetch(
    `https://azmus-crm.onrender.com/orders/${order.id}?status=${newStatus}`,
    {
      method: "PUT",
    }
  );

}}
                  className={`px-5 py-3 rounded-2xl text-white

                  ${order.status === "Yangi" ? "bg-blue-500" : ""}
                  ${order.status === "Kesish" ? "bg-yellow-500" : ""}
                  ${order.status === "Svarka" ? "bg-orange-500" : ""}
                  ${order.status === "Kraska" ? "bg-purple-500" : ""}
                  ${order.status === "Upakofka" ? "bg-pink-500" : ""}
                  ${order.status === "Tayyor" ? "bg-green-500" : ""}
                  `}
                >

                  <option>Yangi</option>
                  <option>Kesish</option>
                  <option>Svarka</option>
                  <option>Kraska</option>
                  <option>Upakofka</option>
                  <option>Tayyor</option>

                </select>

                <div className="flex items-center gap-5">

                  <div className="font-black text-green-600 text-xl">
                    {order.amount} so'm
                  </div>

                  <button

                    onClick={async () => {

                      try {

                        await fetch(
                          `https://azmus-crm.onrender.com/orders/${order.id}`,
                          {
                            method: "DELETE",
                          }
                        );

                        const filtered = orders.filter(
                          (item) => item.id !== order.id
                        );

                        setOrders(filtered);

                      } catch (error) {

                        console.log(error);

                      }

                    }}

                    className="bg-red-500 text-white px-5 py-3 rounded-2xl"
                  >
                    O‘chirish
                  </button>

                </div>

              </div>

            ))}

          </div>

        </div>

      </div>

      {showModal && (

        <div className="fixed inset-0 bg-black/40 flex items-center justify-center">

          <div className="bg-white rounded-[40px] p-8 w-[95%] md:w-[500px]">


            <div className="space-y-4">

              <input
                value={client}
                onChange={(e) => setClient(e.target.value)}
                placeholder="Mijoz nomi"
                className="w-full border rounded-2xl px-5 py-4"
              />

              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="Telefon"
                className="w-full border rounded-2xl px-5 py-4"
              />

              <input
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="Summa"
                className="w-full border rounded-2xl px-5 py-4"
              />

              <button
                onClick={addOrder}
                className="w-full bg-black text-white py-4 rounded-2xl font-bold"
              >
                Saqlash
              </button>

            </div>

          </div>

        </div>

      )}

    </div>

  );
}

export default App;