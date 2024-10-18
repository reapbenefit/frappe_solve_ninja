frappe.ready(function () {
	// frappe.web_form.validate = () => {
	//   let data = frappe.web_form.get_values();
	//   if (data.title.length > 70) {
	// 	frappe.msgprint("Please restrict title to max 70 characters.");
	// 	return false;
	//   }
	//   if (frappe.web_form.get_value("user") && !(frappe.utils.validate_type(frappe.web_form.get_value("user"), "email"))) {
	// 	frappe.msgprint('Invalid email address');
	// 	return false;
	//   }
  
	// };
  
	// frappe.web_form.on("title", (field, value) => {
	//   console.log(value)
	//   if (value.length > 70) {
	// 	frappe.msgprint(`Please restrict the title to max 70 characters, <br> You've entered ${value.length} characters in the title`);
	//   }
	// });
  
	// $('*[data-fieldname="title"]').attr("maxlength", "70");
  
  
	// hide / show fields based on user login information
	// if (frappe.session.user && frappe.session.user != "Guest") {
	//   frappe.web_form.set_value(["user"], frappe.session.user);
	//   frappe.web_form.set_df_property("user", "hidden", 1);
	//   frappe.web_form.set_df_property("anonymous", "hidden", 1);
	// } else {
	//   frappe.web_form.set_df_property("user", "reqd", 1);
	//   frappe.web_form.on("anonymous", (field, checked) => {
	// 	if (!checked) {
	// 	  frappe.web_form.set_value(["user"], "");
	// 	  frappe.web_form.set_df_property("user", "hidden", 0);
	// 	  frappe.web_form.set_df_property("user", "reqd", 1);
	// 	} else {
	// 	  frappe.web_form.set_value(["user"], "");
	// 	  frappe.web_form.set_df_property("user", "hidden", 1);
	// 	  frappe.web_form.set_df_property("user", "reqd", 0);
	// 	}
	//   });
	//   frappe.web_form.set_df_property("user", "hidden", 0);
	// }
  
	// default starting position for map
	let defaultPosition = [22.1458, 80.0882];
  
	if (navigator.geolocation) {
	  navigator.geolocation.getCurrentPosition(showMap, showMap);
	} else {
	  showMap(null);
	}
  
	function showMap(position) {
	  if (position) {
		if (position.coords) {
		  let lat = position.coords.longitude;
		  let long = position.coords.latitude;
		  defaultPosition = [];
		  defaultPosition.push(lat);
		  defaultPosition.push(long);
		}
	  }
	  const container = document.getElementById("map");
	  if (container) {
  
		const screenWidth = window.screen.width;
  
		let mapZoom = 5.4
		if (screenWidth < 700) {
		  mapZoom = 4
		}
		let map = L.map("map").setView(defaultPosition, mapZoom);
  
		L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
		  maxZoom: 19,
		  attribution:
			'&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>',
		}).addTo(map);
		let allMarkers = [];
		map
		  .locate({
			setView: true,
		  })
		  .on("locationerror", function (e) {
			console.log(e);
		  });
  
		function onMapClick(e) {
		  for (let step = 0; step < allMarkers.length; step++) {
			map.removeLayer(allMarkers[step]);
		  }
		  const latlng = e.latlng;
		  frappe.web_form.set_value(["latitude"], latlng.lat);
		  frappe.web_form.set_value(["longitude"], latlng.lng);
  
		  let marker = L.marker([latlng.lat, latlng.lng]).addTo(map);
		  allMarkers.push(marker);
		}
		map.on("click", onMapClick);
	  }
	}
  });
  