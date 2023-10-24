$( document ).ready(function() {

    $("#add").click(function() {
        var description = $("#description").val();
        var cost = $("#cost").val();
        var quantity = $("#quantity").val();
        var descriptionContent = `<input type="text" name="description" value="${description}">`;
        var costContent = `<input type="number" name="cost" value="${cost}">`;
        var quantityContent = `<input type="number" name="quantity" value="${quantity}">`;
        var content = "<tbody><tr><td><input type='checkbox' name='product'></td><td>" + descriptionContent + "</td><td>" + costContent + "</td><td>" + quantityContent + "</td></tr></tbody>";
        if (description !== "" && cost !== "" && quantity !== "") {
            $(".table").append(content);
        } else { 
            $("#description").val("Please fill in")
        }
    });

    $("#remove").click(function() {
        $(".table").find('input[name="product"]').each(function() {
            if($(this).is(":checked")){
                $(this).parents("tr").remove();
            }
        });
    });

    $('#search-invoice').DataTable();

    $("#delete").click(function() {
        $("#delete").hide();
        $("#confirm").show();
    });


    $('input[name="invoice"]').click(function(){
        $("#search-invoice").find('input[name="invoice"]').each(function() {
            if($(this).is(":checked")){
                var num = $(this).parent().siblings(":first").text();
                $('input[name="export-number"]').val(num)
            }
        });
    });

});



