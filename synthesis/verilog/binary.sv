// MAC: multiply-accumulate for binary INT8 neural network inference
module mac_binary_int8 (
    input                    clk, rst,
    input  signed [7:0]      a, b,
    output reg signed [15:0] acc
);
    always_ff @(posedge clk) begin
        if (rst) acc <= 0;
        else     acc <= acc + (a * b);
    end
endmodule
